"""Summarize a Mesen map-transition log and expose its longest route."""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("transitions", type=Path)
    parser.add_argument("--write-targets", type=Path)
    args = parser.parse_args()
    edges: Counter[tuple[str, str]] = Counter()
    with args.transitions.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) >= 3 and row[1] != "from_hash":
                edges[(row[1], row[2])] += 1
    outgoing: dict[str, list[str]] = defaultdict(list)
    for (source, target), count in edges.items():
        outgoing[source].append(target)
    best: list[str] = []
    for start in outgoing:
        route, seen = [], set()
        node = start
        while node not in seen:
            seen.add(node)
            route.append(node)
            targets = sorted(outgoing.get(node, ()), key=lambda t: edges[(node, t)], reverse=True)
            if not targets:
                break
            node = targets[0]
        if len(route) > len(best):
            best = route
    print("edge_count\t%d" % sum(edges.values()))
    print("unique_edges\t%d" % len(edges))
    print("longest_route\t%d" % len(best))
    print("route\t" + " -> ".join(best))
    terminals = sorted({target for _, target in edges} - set(outgoing))
    print("terminal_candidates\t%d" % len(terminals))
    if args.write_targets:
        args.write_targets.write_text(
            "\n".join(f"{node}\t0" for node in terminals) + "\n",
            encoding="utf-8",
        )
    print("repeated_edges")
    for (source, target), count in edges.most_common():
        if count > 1:
            print(f"{source}\t{target}\t{count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
