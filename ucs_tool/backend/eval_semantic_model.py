import argparse
import json

from ucs_service import MATCHER


DEFAULT_PROMPTS = [
    "坚硬的石头撞击地面",
    "石块砸到地面",
    "岩石掉落撞击",
    "金属刀摩擦",
    "雨打金属屋顶",
    "木头快速生长魔法",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate ENZ UCS matching with the optional embedding model."
    )
    parser.add_argument("prompts", nargs="*", help="Chinese prompts to evaluate.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON results.")
    return parser.parse_args()


def main():
    args = parse_args()
    prompts = args.prompts or DEFAULT_PROMPTS

    print("Model status:")
    print(json.dumps(MATCHER.model_status(), ensure_ascii=False, indent=2))
    print()

    for prompt in prompts:
        result = MATCHER.parse(prompt)
        if args.json:
            print(json.dumps({"prompt": prompt, "result": result}, ensure_ascii=False, indent=2))
            continue

        data = result.get("data") or {}
        print(prompt)
        for candidate in (data.get("candidates") or [])[:3]:
            line = (
                f"  {candidate['ucs_prefix']:<10} score={candidate['score']:<6} "
                f"rule={candidate.get('rule_score', 0):<5} "
                f"light={candidate.get('semantic_score', 0):<5} "
                f"fts={candidate.get('fts_score', 0):<5} "
                f"model={candidate.get('embedding_score', 0):<5} "
                f"{candidate.get('zh_category', '')}/{candidate.get('zh_subcategory', '')}"
            )
            print(line)
            terms = ", ".join(candidate.get("matched_terms") or [])
            if terms:
                print(f"    {terms}")
        print()


if __name__ == "__main__":
    main()
