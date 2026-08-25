"""python -m attacks [--sabotage] [--write] [--markdown]"""
import sys
from pathlib import Path

from . import report, runner

RESULTS = Path(__file__).resolve().parent / "RESULTS.md"


def main(argv):
    sabotage = "--sabotage" in argv

    if "--write" in argv or "--markdown" in argv:
        sabotaged = runner.run(post_validation=False)
        guarded = runner.run(post_validation=True,
                             mark_releases=runner.releasing_ids(sabotaged))
        guarded_summary = runner.summarise(guarded)
        text = report.markdown(guarded, sabotaged, guarded_summary,
                               runner.summarise(sabotaged))
        if "--write" in argv:
            RESULTS.write_text(text, encoding="utf-8")
            print(f"written {RESULTS}")
        else:
            print(text)
        return 0

    results = runner.run(post_validation=not sabotage)
    summary = runner.summarise(results)
    if sabotage:
        print("!! post-validation disabled — failure-mode demonstration\n")
    for result in results:
        mark = "blocked" if result["blocked"] else "PASSED "
        print(f"  {mark}  {result['id']:<22} {result['observed']:<15} "
              f"{', '.join(result['evidence'])[:60]}")
    print(f"\n  cases              {summary['cases']} "
          f"({summary['input_cases']} input, {summary['model_cases']} model)")
    print(f"  blocked            {summary['blocked']}/{summary['cases']}")
    print(f"  silently released  {summary['silently_released']}"
          f"  {summary['released_outputs'] or ''}")
    return 0 if summary["silently_released"] == 0 or sabotage else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
