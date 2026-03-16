from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests


WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"


@dataclass
class WikidataConfig:
    endpoint: str = WIKIDATA_SPARQL_ENDPOINT
    user_agent: str = "PoBL-MinPoG/0.1 (https://example.invalid; research)"
    timeout_s: int = 60
    sleep_s_between_requests: float = 0.1  # be polite to the public endpoint


class WikidataClient:
    def __init__(self, cfg: WikidataConfig | None = None):
        self.cfg = cfg or WikidataConfig()
        self._last_request_t = 0.0

    def sparql(self, query: str) -> Dict:
        # minimal rate limiting
        now = time.time()
        wait_s = self.cfg.sleep_s_between_requests - (now - self._last_request_t)
        if wait_s > 0:
            time.sleep(wait_s)

        headers = {
            "Accept": "application/sparql-results+json",
            "User-Agent": self.cfg.user_agent,
        }
        r = requests.get(
            self.cfg.endpoint,
            params={"query": query, "format": "json"},
            headers=headers,
            timeout=self.cfg.timeout_s,
        )
        r.raise_for_status()
        self._last_request_t = time.time()
        return r.json()

    def search_entity(self, text: str, limit: int = 5, lang: str = "en") -> List[Tuple[str, str]]:
        """
        Very small entity linker: use Wikidata label matching via SPARQL.
        Returns list of (QID, label).
        """
        q = f"""
SELECT ?item ?itemLabel WHERE {{
  ?item rdfs:label "{_escape(text)}"@{lang}.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang}". }}
}}
LIMIT {int(limit)}
"""
        data = self.sparql(q)
        out: List[Tuple[str, str]] = []
        for b in data.get("results", {}).get("bindings", []):
            item = b["item"]["value"]
            qid = item.rsplit("/", 1)[-1]
            label = b.get("itemLabel", {}).get("value", qid)
            out.append((qid, label))
        return out

    def list_predicates_around_entity(self, qid: str, limit: int = 80) -> List[str]:
        """
        Enumerate wdt:Pxxx predicates connected to the entity as subject or object.
        This is the Wikidata replacement for Freebase relation list.
        """
        q = f"""
SELECT DISTINCT ?p WHERE {{
  {{
    wd:{qid} ?p ?o .
    FILTER(STRSTARTS(STR(?p), "http://www.wikidata.org/prop/direct/"))
  }}
  UNION
  {{
    ?s ?p wd:{qid} .
    FILTER(STRSTARTS(STR(?p), "http://www.wikidata.org/prop/direct/"))
  }}
}}
LIMIT {int(limit)}
"""
        data = self.sparql(q)
        preds: List[str] = []
        for b in data.get("results", {}).get("bindings", []):
            p_iri = b["p"]["value"]
            # map to wdt:Pxx form (direct claim)
            pid = p_iri.rsplit("/", 1)[-1]
            preds.append(f"wdt:{pid}")
        preds = sorted(list(set(preds)))
        return preds

    def expand_triples(
        self,
        qid: str,
        predicate: str,
        direction: str = "out",
        limit: int = 20,
        lang: str = "en",
    ) -> List[Tuple[str, str, str, str]]:
        """
        Expand one hop triples for a given entity and predicate.
        Returns list of (sub_qid, sub_label, pred, obj_label_or_value)
        """
        if not predicate.startswith("wdt:P"):
            raise ValueError(f"predicate must be like 'wdt:P31', got {predicate}")

        if direction == "out":
            q = f"""
SELECT ?o ?oLabel WHERE {{
  wd:{qid} {predicate} ?o .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang}". }}
}}
LIMIT {int(limit)}
"""
        elif direction == "in":
            q = f"""
SELECT ?s ?sLabel WHERE {{
  ?s {predicate} wd:{qid} .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang}". }}
}}
LIMIT {int(limit)}
"""
        else:
            raise ValueError("direction must be 'out' or 'in'")

        data = self.sparql(q)
        triples: List[Tuple[str, str, str, str]] = []
        for b in data.get("results", {}).get("bindings", []):
            if direction == "out":
                o = b["o"]["value"]
                o_label = b.get("oLabel", {}).get("value", o.rsplit("/", 1)[-1])
                triples.append((qid, qid, predicate, o_label))
            else:
                s = b["s"]["value"]
                s_qid = s.rsplit("/", 1)[-1]
                s_label = b.get("sLabel", {}).get("value", s_qid)
                triples.append((s_qid, s_label, predicate, qid))
        return triples


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')

