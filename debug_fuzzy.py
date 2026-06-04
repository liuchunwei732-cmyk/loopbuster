"""Debug script for fuzzy_repeat detection."""
import sys
sys.path.insert(0, '.')
from benchmark.evaluate import evaluate_trajectory, load_scenarios
from loopbuster import ActionConfig, LoopBuster

lb = LoopBuster(
    similarity_threshold=0.85,
    action_config=ActionConfig(warn_threshold=1, stop_threshold=4, escalate_threshold=6),
)

trajs = load_scenarios('benchmark/scenarios')
fuzzy = [t for t in trajs if t['task_category'] == 'fuzzy_repeat']
print(f'Total fuzzy: {len(fuzzy)}')
detected = 0
for t in fuzzy:
    r = evaluate_trajectory(t, lb)
    if r['detected']:
        detected += 1
    else:
        print(f"FN: {t['trajectory_id']} steps={r['total_steps']} tools={[a['tool'] for a in t['actions'][:4]]}")
        break
print(f'Detected: {detected}/{len(fuzzy)}')
