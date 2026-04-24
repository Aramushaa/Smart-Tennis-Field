# HAR Model Evaluation — Results

## 1. Evaluation Setup

| Parameter | Value |
|-----------|-------|
| Model | `L2MU_plain_leaky.onnx` (PyTorch 2.2.1, ONNX opset 17, 3230 nodes) |
| Input shape | `[40, 1, 6]` — 40 timesteps × 1 batch × 6 features |
| Output shape | `[40, 1, 7]` — per-timestep prediction, 7 classes |
| Device filter | `watch` only |
| Input layout | `gyro_then_accel` |
| Temporal preprocessing | `none` |
| Score aggregation | `sum` across all 40 timesteps |
| Window size | 40 samples |
| Window stride | 20 samples |
| Recordings per activity | 5 (round-robin window selection) |
| Fetch limit per recording | 1,000 rows |
| Max windows per activity | 20 |
| Total windows evaluated | 140 (7 activities × 20 windows) |

---

## 2. Per-Activity Accuracy (7 Supported Activities)

| Code | Activity | Correct / Total | Accuracy | Dominant Misclassification |
|------|----------|----------------|----------|---------------------------|
| F | Typing | 16/20 | **80.0%** | writing (10%), folding (10%) |
| G | Brushing Teeth | 17/20 | **85.0%** | folding (10%), catch (5%) |
| O | Playing Catch (Tennis) | 19/20 | **95.0%** | dribbling (5%) |
| P | Dribbling (Basketball) | 19/20 | **95.0%** | folding (5%) |
| Q | Writing | 13/20 | **65.0%** | folding (30%), typing (5%) |
| R | Clapping | 18/20 | **90.0%** | catch (5%), typing (5%) |
| S | Folding Clothes | 17/20 | **85.0%** | typing (5%), writing (5%), catch (5%) |

### Overall Accuracy

**119/140 = 85.0%**

---

## 3. Prediction Distribution (All 18 Siddha Activities)

The evaluation also tested the model on all 18 activities present in the database to characterize its behavior on unsupported inputs.

| Code | Activity | In Model? | Prediction Distribution |
|------|----------|-----------|------------------------|
| A | Walking | NO | catch 60%, folding 30%, dribbling 10% |
| B | Jogging | NO | catch 70%, dribbling 30% |
| C | Stairs | NO | catch 45%, folding 35%, typing 15%, teeth 5% |
| D | Sitting | NO | writing 30%, typing 30%, teeth 15%, catch 15%, folding 10% |
| E | Standing | NO | folding 35%, writing 25%, catch 20%, typing 10%, teeth 10% |
| **F** | **Typing** | **YES** | **typing 80%**, writing 10%, folding 10% |
| **G** | **Brushing Teeth** | **YES** | **teeth 85%**, folding 10%, catch 5% |
| H | Eating Soup | NO | folding 40%, catch 25%, writing 20%, typing 10%, teeth 5% |
| I | Eating Chips | NO | typing 45%, teeth 20%, folding 15%, writing 15%, clapping 5% |
| J | Eating Pasta | NO | typing 30%, folding 30%, catch 25%, writing 10%, teeth 5% |
| K | Drinking from Cup | NO | writing 40%, folding 30%, catch 15%, teeth 10%, typing 5% |
| L | Eating Sandwich | NO | teeth 50%, catch 25%, folding 20%, clapping 5% |
| M | Kicking (Soccer) | NO | catch 65%, folding 35% |
| **O** | **Playing Catch (Tennis)** | **YES** | **catch 95%**, dribbling 5% |
| **P** | **Dribbling (Basketball)** | **YES** | **dribbling 95%**, folding 5% |
| **Q** | **Writing** | **YES** | **writing 65%**, folding 30%, typing 5% |
| **R** | **Clapping** | **YES** | **clapping 90%**, catch 5%, typing 5% |
| **S** | **Folding Clothes** | **YES** | **folding 85%**, typing 5%, writing 5%, catch 5% |

### Observations on Unsupported Activities

For the 11 activities not in the model's training set, predictions are distributed across the 7 known labels. The model tends to classify:

- High-motion activities (Walking, Jogging, Kicking) as **catch** or **dribbling** — reasonable since these are the most dynamic in-model activities
- Stationary/fine-motor activities (Sitting, Standing, Eating) as **writing**, **typing**, **folding**, or **teeth** — the model maps them to similar low-motion patterns
- This behavior is expected: the model has no "unknown" class, so it maps unseen activities to the closest learned pattern

---

## 4. Key Findings

### The Model Works Correctly

The initial evaluation (from the earlier debugging phase) showed only ~15% accuracy because of critical data handling errors:

1. **Mixed-device windows** — phone and watch data were combined in the same window
2. **Wrong input layout** — accelerometer-first instead of gyroscope-first
3. **Wrong evaluation scope** — testing 7-class model against all 18 activities

After fixing these issues, the model demonstrates **strong classification performance (85.0%)** on its intended scope.

### Performance Tiers

| Tier | Activities | Accuracy Range |
|------|-----------|----------------|
| Excellent (≥90%) | Catch, Dribbling, Clapping | 90–95% |
| Good (80–89%) | Typing, Brushing Teeth, Folding Clothes | 80–85% |
| Moderate (< 80%) | Writing | 65% |

### Writing Activity (Q) Is Weakest

Writing achieves only 65%, with 30% of windows misclassified as Folding Clothes. This suggests the wrist motion patterns for writing and folding are similar in the model's feature space.

---

## 5. Evaluation Methodology

### Round-Robin Window Selection

Windows are distributed evenly across 5 recording sessions per activity to avoid bias toward any single recording. Each recording contributes 4 windows to the total of 20 per activity.

### Confidence Analysis

Most correct predictions show high confidence (>80%). Misclassifications tend to have lower confidence, suggesting the model's probability calibration is reasonable.

---

## 6. Evaluation Scripts

| Script | Purpose |
|--------|---------|
| `evaluate_model.py` | Comprehensive evaluation across all activities |
| `inspect_model.py` | ONNX model architecture inspection |
| `fix_finder.py` | Exhaustive search across aggregation, input format, label order, device |

All scripts are located in `services/har_service/`.
