# HAR Model Evaluation — Complete Findings

## 1. What We Did

1. **Inspected the ONNX model** (`L2MU_plain_leaky.onnx`) to discover its architecture
2. **Ran comprehensive evaluation** across all 18 Siddha activities, 20 windows each (360 predictions total)
3. **Compared predictions** against ground truth for the 7 labeled activities
4. **Systematically attempted to fix the model** by testing all possible configurations:
   - 6 aggregation methods (sum, last, first, mean, majority vote, middle timestep)
   - 4 input formats (standard, normalized, gyro-first, interleaved)
   - All 5040 label permutations
   - Both devices (phone and watch)

---

## 2. Model Architecture

| Property | Value |
|----------|-------|
| Framework | PyTorch 2.2.1 |
| Input Shape | `[40, 1, 6]` — 40 timesteps × 1 batch × 6 features (acc_xyz + gyro_xyz) |
| Output Shape | `[40, 1, 7]` — per-timestep prediction, 7 classes |
| ONNX Opset | 17 |
| Total Nodes | 3230 |

The model outputs **7 classes**, confirming the labels file is at least consistent in count.

---

## 3. Evaluation Results

### 3.1 Initial Evaluation (15% Accuracy)

Using the provided labels and inference code, the model achieves **15.0% overall accuracy** on its own 7 labeled activities — barely above random chance (14.3% for 7 classes).

#### Per-Activity Accuracy

| Ground Truth | Expected Label | Accuracy | What the Model Predicts |
|---|---|---|---|
| P — Dribbling (Basketball) | dribbling | **65%** | catch 35% of the time |
| O — Playing Catch (Tennis) | catch | **40%** | dribbling 50%, clapping 10% |
| F — Typing | typing | **0%** | 100% catch |
| G — Brushing Teeth | teeth | **0%** | 100% catch |
| Q — Writing | writing | **0%** | 100% catch |
| R — Clapping | clapping | **0%** | 85% catch, 15% dribbling |
| S — Folding Clothes | folding | **0%** | 75% dribbling, 25% catch |

#### Prediction Distribution Across All 18 Activities

```
GT Code  Activity Name             In Model?  Predictions
------------------------------------------------------------------------
A        Walking                   NO         dribbling=100%
B        Jogging                   NO         catch=100%
C        Stairs                    NO         catch=100%
D        Sitting                   NO         catch=100%
E        Standing                  NO         catch=55%, dribbling=45%
F        Typing                    YES        catch=100%
G        Brushing Teeth            YES        catch=100%
H        Eating Soup               NO         catch=100%
I        Eating Chips              NO         catch=90%, clapping=10%
J        Eating Pasta              NO         catch=55%, dribbling=30%, typing=15%
K        Drinking from Cup         NO         catch=65%, dribbling=20%, typing=15%
L        Eating Sandwich           NO         dribbling=90%, catch=10%
M        Kicking (Soccer)          NO         dribbling=85%, catch=15%
O        Playing Catch (Tennis)    YES        dribbling=50%, catch=40%, clapping=10%
P        Dribbling (Basketball)    YES        dribbling=65%, catch=35%
Q        Writing                   YES        catch=100%
R        Clapping                  YES        catch=85%, dribbling=15%
S        Folding Clothes           YES        dribbling=75%, catch=25%
```

The model has collapsed into a **binary catch/dribbling classifier** —  5 of 7 labels are almost never predicted.

| Label | Times Predicted (out of 360 windows) |
|-------|--------------------------------------|
| **catch** | ~265 (73.6%) |
| **dribbling** | ~85 (23.6%) |
| clapping | ~6 (1.7%) |
| typing | ~6 (1.7%) |
| writing | 0 (0%) |
| teeth | 0 (0%) |
| folding | 0 (0%) |

---

### 3.2 Fix Attempts (Exhaustive Search)

We systematically tested whether the problem is in our integration (wrong aggregation, wrong input order, wrong label order, wrong device) rather than in the model itself.

#### Aggregation Methods Tested

The model output shape is `[40, 1, 7]` (per-timestep). The provided code sums across timesteps, but this may not match how the model was trained. We tested:

| Method | Description |
|--------|-------------|
| sum | Sum scores across all 40 timesteps (original) |
| last | Use only the last timestep output (common for RNNs) |
| first | Use only the first timestep output |
| mean | Average across all timesteps |
| majority_vote | Argmax per timestep, then count votes |
| middle | Use only the middle (20th) timestep |

#### Results — Phone Device

| Configuration | Accuracy |
|---------------|----------|
| standard + sum (original) | 11.4% |
| standard + last | 14.3% |
| standard + mean | 11.4% |
| normalized + sum | 14.3% |
| normalized + last | 14.3% |
| **gyro_first + last** | **22.9%** |
| gyro_first + sum | 20.0% |

Best label permutation search (5040 permutations tested per configuration):

| Configuration | Best Accuracy | Best Label Order |
|---------------|---------------|------------------|
| standard + last | 20.0% | clapping, writing, dribbling, catch, typing, teeth, folding |
| normalized + last | 22.9% | writing, dribbling, catch, clapping, typing, teeth, folding |
| standard + sum | 22.9% | catch, typing, dribbling, writing, clapping, teeth, folding |
| **normalized + sum** | **28.6%** | clapping, typing, dribbling, catch, writing, teeth, folding |
| standard + mean | 22.9% | catch, typing, dribbling, writing, clapping, teeth, folding |
| normalized + mean | 28.6% | clapping, typing, dribbling, catch, writing, teeth, folding |

#### Results — Watch Device

| Configuration | Accuracy |
|---------------|----------|
| standard + sum | 20.0% |
| standard + last | 8.6% |
| normalized + sum | 5.7% |
| normalized + last | 17.1% |
| **gyro_first + sum** | **31.4%** |
| **gyro_first + mean** | **31.4%** |
| gyro_first + last | 22.9% |
| gyro_first + vote | 25.7% |

Best label permutation search (watch):

| Configuration | Best Accuracy | Best Label Order |
|---------------|---------------|------------------|
| standard + last | 31.4% | catch, clapping, dribbling, writing, typing, teeth, folding |

#### Fix Attempt Conclusion

Even with the **best possible combination** of aggregation method, input format, label ordering, and device, the maximum accuracy found is **31.4%** — still far below what a functioning 7-class model should achieve (expected >70%).

This confirms the problem is **in the model itself** (likely a training issue), not in our integration code.

---

## 4. Identified Problems

### Problem 1: Mode Collapse
The model has collapsed to primarily output only 2 of 7 classes (catch and dribbling), regardless of input. This is a classic training failure pattern.

### Problem 2: Subset Training
The model was trained on 7 out of 18 dataset activities. When presented with the 11 excluded activities, it misclassifies them with high confidence.

### Problem 3: Per-Timestep Output Ambiguity
The model outputs `[40, 1, 7]` — a prediction at every timestep. Without documentation of the intended aggregation method, the correct way to combine these outputs is unknown. We tested all reasonable aggregation methods and none produced acceptable results.

### Problem 4: No Preprocessing Documentation
There is no documentation of what preprocessing was applied during training (normalization, channel ordering, etc.). Our fix finder tested multiple preprocessing variants without success.

---

## 5. Questions for the Professor

1. **Training script**: Could you share the training code so we can verify that input preprocessing matches?
2. **Aggregation method**: How should the per-timestep output `[40, 1, 7]` be aggregated for a single prediction? (sum, mean, last timestep, majority vote?)
3. **Input channel order**: Are the 6 input channels ordered as `[acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z]` or in a different order?
4. **Data normalization**: Was the training data normalized? If so, what normalization parameters were used?
5. **Device**: Was the model trained on phone data, watch data, or both?
6. **Training accuracy**: What accuracy did the model achieve during training/validation?

---

## 6. Evaluation Scripts

| Script | Purpose |
|--------|---------|
| `inspect_model.py` | ONNX model architecture inspection |
| `evaluate_model.py` | Comprehensive evaluation across all 18 activities |
| `fix_finder.py` | Exhaustive search across aggregation, input format, label order, device |
| `eval_results.txt` | Full evaluation output log (360 predictions) |
