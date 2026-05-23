# Practical Tips for Photonic Inverse Design



## 1. Formulate the problem before touching the optimizer

The single most common mistake in inverse design is starting the optimization before the problem is well-posed. Before you run a single gradient step, be able to answer all of the following:

**What exactly is the figure of merit (FOM)?**
Write it as a single scalar function, if you cannot write it down cleanly, you still need to work on defining what exactly you want your FOM to be.

**What are the constraints, and are they in the FOM or enforced separately?**
Fabrication constraints (minimum feature size, binary permittivity) should be enforced via the density filter and projection pipeline, not the FOM. Physical constraints (e.g., energy conservation, reciprocity) should be used to simplify or verify the FOM, not to add extra penalty terms.

**Are there degenerate solutions?**
Ask: is there a trivial design that scores well on your FOM without doing what you actually want? The empty design (all air) is the most common degenerate solution when fabrication penalties are too aggressive or the power terms are missing. All-Si₃N₄ (all filled) is another. If either of these trivially optimizes your FOM, add a term that breaks the degeneracy before running anything.

**What does the landscape look like qualitatively?**
Think about what happens as you move from the initial design toward likely optima. Is the path smooth? Are there obvious symmetries the optimizer should respect? Understanding this analytically takes 30 minutes and can save 100s of FlexCredits.

---

## 2. Start simple and scale up

Never begin with the full-resolution, full-complexity version of your problem. Always prototype first.

**Reduce the design region.** If your final device is 30 µm × 30 µm at 20 nm resolution (2.25 million parameters), start with 10 µm × 10 µm (250,000 parameters). The physics still works, the gradients still flow, and you can run 20 iterations for a fraction of the cost. Use the small version to validate the FOM, the density filter, the source geometry, and the optimizer settings before scaling up.

**Reduce the number of channels.** If you want an N-channel device, design a 2-channel device first. The 2-channel objective is simpler, easier to interpret, and faster to converge. If the 2-channel case does not work, the N-channel case definitely will not.

**Use a coarser grid.** A 40 nm grid runs roughly 8× faster than a 20 nm grid (3D volume scales as the cube of linear resolution). At early stages of development, coarser is fine — you are testing the FOM and optimizer behavior, not resolving sub-wavelength features.

**Check cost before committing.** Every serious FDTD platform has a cost-estimation API. Call it on your initial simulation before starting the optimization loop. Multiply by the number of simulations per iteration and the number of iterations. If the estimate surprises you, investigate the mesh — an accidental global fine-mesh override is the most common cause of inflated cost.

---

## 3. The density filter and projection pipeline

This pipeline is the backbone of fabricable topology optimization. Understanding each stage prevents a large class of debugging problems.

### The pipeline in order:

1. **Raw parameters** `ρ ∈ [0, 1]^(nx × ny)` — the actual optimization variables.
2. **Symmetry enforcement** (if applicable) — average `ρ` with its mirror copy. Reduces effective parameter count and bakes in physical symmetry. Apply before the filter.
3. **Interface buffers** — force `ρ = 1` or `ρ = 0` in specific regions where the design must connect to fixed structures (waveguide stubs, metal contacts, etc.). These are hard constraints.
4. **Spatial filter** — conic or Gaussian filter of radius `r_min` (the minimum feature size you want to enforce). This smears out single-pixel spikes that fabrication cannot reproduce.
5. **Heaviside projection** — maps the filtered density toward binary via a smoothed step with sharpness `β`. Low `β` (~1) is nearly linear; high `β` (~30) is nearly a step function.
6. **Rescale** — map from [0,1] to [ε_min, ε_max].

### Key rules:

- **Apply the filter before the projection, always.** Applying the projection first then the filter undoes the projection and defeats the purpose.
- **Apply the pipeline twice.** A single filter+project pass can miss features that only become too-small after binarization. Running the full pipeline twice in series provides stronger minimum-feature-size guarantees.
- **The filter radius should match your fabrication constraint, not your grid size.** If your fab process has a 100 nm minimum feature, set `r_min = 100 nm` regardless of whether your grid is 20 nm or 10 nm. The filter operates in physical units.
- **After any change to the design region size or grid resolution, recheck the filter radius in units of grid cells.** The filter kernel is usually specified in physical units, but it is implemented in pixel space. If you change the resolution, verify that the physical radius maps to the right number of pixels.

---

## 4. Beta annealing: the most important hyperparameter to get right

`β` (the Heaviside projection sharpness) is the single parameter with the most impact on whether your optimization succeeds. Getting its schedule right is more important than the learning rate.

### The intuition

At `β = 1`, the projection is nearly linear. Every intermediate value of `ρ` (say 0.4 or 0.7) maps to a meaningful intermediate permittivity. The optimizer sees a smooth landscape and can move freely. At `β = 30`, the projection is nearly a step function. Only values very close to 0 or 1 survive; everything else gets pushed hard to the boundary. The landscape becomes nearly discrete, and the optimizer can barely move.

The annealing schedule exploits this: start soft to find good topology, then harden to force a binary fabricable result.

### Recommended schedule

- **Phase 1 (soft, `β = 1`):** Run for roughly 15–20% of total iterations. The goal is to form large-scale structure — where the high-ε and low-ε regions should roughly be. Do not rush this phase.
- **Phase 2 (ramp, `β = 1 → β_max`):** Linearly increase `β` over the remaining ~80% of iterations. The ramp should be slow enough that the optimizer can continuously adjust the topology as it binarizes. A jump directly from 1 to 30 is too abrupt.
- **`β_max`:** Usually 30–50 is sufficient. Beyond 50 you are just wasting optimizer steps — the design is already functionally binary.

### How to tell if the schedule is wrong

| Symptom | Cause | Fix |
|---|---|---|
| Design looks like random noise at iteration 0, never improves | `β_max` applied too early | Extend soft phase; don't start ramp until structure is visible |
| Design converges in phase 1 then degrades during ramp | Topology can't be binarized cleanly | Start ramp later, ramp more slowly, or increase filter radius |
| Design is still gray (not binary) at the end | `β_max` too low, or too few iterations in phase 2 | Increase `β_max` to 50, or extend the ramp |
| Objective improves but design fails validation | Gray intermediate values look fine in simulation but fail when binarized post-hoc | Run your final evaluation with `β_max` applied explicitly and parameters clipped to `{0,1}` |

---

## 5. Designing the objective function

### The basic structure

Almost every well-posed inverse design objective has the form:

```
J = (efficiency terms) - λ_constraint · (constraint violation terms) - P_fab(ρ)
```

The efficiency terms reward coupling power from the source to the target. The constraint terms penalize whatever physical behavior you want to suppress (crosstalk, reflections, unwanted modes). The fabrication penalty discourages intermediate-density or sub-resolution features.

### Balancing the weights

The most common mistake is setting all weights to 1.0 without checking whether the terms have comparable magnitudes. If your efficiency term typically has magnitude 0.5 (50% coupling) and your crosstalk term has magnitude 0.001, a weight of `λ = 1.0` means the optimizer almost entirely ignores the crosstalk. Check the magnitude of each term on the initial design and normalize accordingly.

A practical diagnostic: at the end of iteration 1, print all three terms separately. If any one of them dominates by more than an order of magnitude, the optimization will effectively ignore the others.

### The degenerate solution test

Before running optimization, evaluate your FOM on three pathological designs:

1. **All zeros** (`ρ = 0` everywhere, all air). What does J return?
2. **All ones** (`ρ = 1` everywhere, all Si₃N₄). What does J return?
3. **Initial random** (`ρ ~ Uniform[0,1]`). What does J return?

If the optimizer could get a higher J by heading toward design 1 or 2 than by actually optimizing, it will do exactly that. Add terms or renormalize to close off these escape routes before running.

### Competing objectives: efficiency vs. orthogonality

When your FOM has two terms that compete (e.g., coupling efficiency and channel orthogonality), they will trade off throughout the run. A few practical observations:

- **High efficiency and low orthogonality** means the optimizer found a design that couples power well but does not separate channels. Increase `λ_orth`.
- **High orthogonality and low efficiency** means the optimizer found the trivial solution of coupling nothing. Decrease `λ_orth` or add a floor on the efficiency term.
- **Good balance early, then diverging late** often means the β ramp is destabilizing the balance. The relative magnitudes of efficiency and orthogonality terms can change as the design binarizes. Monitor both terms separately at every iteration, not just the total J.

### Fabrication penalty: when to use it and when to turn it off

The erosion–dilation fabrication penalty (`make_erosion_dilation_penalty` in Tidy3D) punishes parameter values that create features below the minimum feature size. It is useful but not always necessary — the density filter already enforces minimum feature size by construction. The penalty adds a softer, gradient-based pressure.

Turn the fabrication penalty **off** for the first 15–20 iterations (while `β` is small and the design is not yet binary). The penalty is most meaningful on nearly-binary designs. On a soft, gray design it just adds noise to the gradient without doing useful work. Re-enable it once `β > 5`.

---

## 6. Choosing and running the optimizer

### Adam is almost always the right choice

Adam (Adaptive Moment Estimation) from `optax` is the standard for inverse design in photonics. It is robust to gradient noise (which FDTD always has), does not require tuning of separate per-parameter learning rates, and converges reliably on high-dimensional smooth objectives. Use it unless you have a specific reason not to.

**Learning rate:** Start with `lr = 0.1–0.2`. If the loss oscillates wildly between iterations, halve it. If it barely moves in phase 1 (the soft phase), double it. The right learning rate moves the loss meaningfully at each step without causing large bounces.

**Parameter clipping:** After every Adam update, clip parameters to `[0, 1]`. Adam's momentum accumulation can push parameters outside this range. Unclipped parameters that go to -0.5 or 1.8 will produce incorrect permittivities when rescaled and confuse the projection.

### Checkpointing

Save the following after every iteration to a pickle file:
- Current parameter array
- All J values (the full loss history)
- All gradient arrays
- The full optax optimizer state (including momentum and variance estimates)
- The β value used at each iteration

**Why optimizer state matters:** If you resume from a checkpoint with only the parameter array, Adam restarts with zero momentum. The first several resumed iterations behave like a cold start — the optimizer takes small, tentative steps before rebuilding momentum. This wastes iterations. With optimizer state saved, the resume is exact.

**Naming convention:** Never overwrite a checkpoint file when starting a new run. Name files with a timestamp or iteration count: `history_v2_iter40.pkl`. One overwrite on a 60-iteration run can cost you 150+ FlexCredits to reconstruct.

---

## 7. Reading the loss curve

Plot your J values after any significant run. Recognizing the phases helps you decide whether to continue, restart, or change hyperparameters.

### The three normal phases

**Phase 1 — rapid initial improvement (soft β, early iterations):**
The optimizer finds the gross layout of the device quickly. Loss should drop noticeably in the first 5–10 iterations. This is the most informationally dense part of the run.

**Phase 2 — reorganization during β ramp:**
As β increases, intermediate-density regions are forced toward binary. The loss often temporarily worsens or plateaus as the topology re-adjusts. This is expected and not a reason to stop. A temporary 5–15% regression in J during this phase is normal.

**Phase 3 — slow convergence toward saturation:**
The design is nearly binary. Improvements are incremental — fine-tuning of feature widths and positions. The loss asymptotes. If it is still falling steeply at your iteration budget, add more iterations.

### Red flags

- **Loss flat from iteration 0:** Gradient is zero or near-zero. The source is not coupling into the design region, or there is a bug in the FOM that returns a constant regardless of ρ. Check gradients explicitly before running more iterations.
- **Loss improves in phase 1 then collapses and never recovers:** β ramp started too early, or the ramp rate is too fast. The optimizer committed to a topology that cannot be binarized.
- **Loss oscillates with no trend:** Learning rate is too high. Reduce by 2×.
- **Loss decreases monotonically but faster after β starts ramping:** This is unusual and usually means the soft-phase result was poor and the β ramp is helping by regularizing. Let it run; it often converges.
- **Loss improves but validation fails completely:** The FOM does not actually capture what you care about. This is a FOM definition problem, not an optimizer problem. Go back to Section 5 and reconsider the objective.

---

## 8. Exploiting physical symmetry

If your device is physically symmetric (mirror symmetry, rotational symmetry), exploiting that symmetry is almost always worth doing. The benefits are:

1. **Reduced parameter count.** Half (or more) of the parameters are determined by the others.
2. **Reduced simulation count.** Symmetric devices can often derive the response of mirror-image sources from one forward simulation, cutting FDTD cost proportionally.
3. **Better-conditioned optimization.** With fewer independent parameters, the gradient is less noisy and the optimizer converges more reliably.

### How to enforce symmetry correctly

Enforce symmetry on the **raw parameters**, before the filter and projection, by averaging `ρ` with its mirror copy:
```python
ρ_sym = (ρ + flip(ρ)) / 2
```
This guarantees that the filtered and projected design is also symmetric, because the filter and projection are applied after the averaging.

Do **not** enforce symmetry after the projection. Averaging two binarized fields can produce intermediate values that then go through the projection again with unpredictable results.

### Validating the symmetry assumption

Before relying on symmetry to skip simulations (e.g., deriving `C_B` from `C_A`), run all sources explicitly on the initial design and verify the symmetry relationship numerically. The relative residual should be below ~1% for the trade to be safe. If the residual is larger, either the source geometry is not exactly symmetric, or the mode-monitor convention introduces a phase that your flip operator does not account for. Fix this before running the full loop — using an incorrect symmetry trade corrupts every gradient computed during optimization.

---

## 9. Interpreting the design visually

Visualize the fully binarized design (`β = β_max`, clipped to `{0, 1}`) at regular checkpoints during the run, not just at the end. Watching the design evolve tells you more than the loss curve alone.

### What a healthy design looks like

- **Clear binary contrast.** Black (high ε) and white (low ε) with minimal gray. If large gray regions persist at high β, the filter radius is too large for the available design space, or the β ramp needs adjustment.
- **Coherent structure.** You should be able to see the physics in the design. A grating coupler should show something grating-like. A beam splitter should show recognizable waveguide traces. If the design looks like random salt-and-pepper noise, the optimizer has not found a coherent solution.
- **Connectivity at interfaces.** Any point where the design region must connect to a fixed structure (waveguide stub, port, contact) should show continuous high-ε material. Disconnections here mean the optimizer has eroded the coupling interface — the device may simulate well but would not function if the optimizer found a shortcut via reduced coupling.

### What a problematic design looks like

- **Salt-and-pepper noise:** β ramp was too fast; topology never formed. Restart with a slower ramp.
- **Large uniform regions adjacent to chaotic narrow ones:** The optimizer has found one part of the solution but is confused about another. Check whether the FOM weights are balanced and all sources are contributing to the gradient.
- **Suspiciously simple design (just horizontal stripes, or uniform filling):** The optimizer may have found a local minimum that trivially satisfies one term while ignoring the rest. Check each FOM term individually — one of them is probably near zero when it should not be.
- **Design identical to initial condition after 10 iterations:** Gradient flow is broken. Debug by checking whether `value_and_grad` returns a non-zero gradient on the initial parameters.

---

## 10. Debugging gradient flow

Broken gradient flow is the hardest class of bug to diagnose because the optimizer appears to run normally — it just does nothing useful.

### Symptom: gradient is zero or near-zero from the start

**Check 1: Is the source actually coupling into the design region?** Run a forward simulation on the initial parameters (without adjoint) and plot the field magnitude. If the field is negligible in the design region, the source is pointing the wrong direction, positioned outside the domain, or blocked by a structure. The adjoint field is also zero in this case, giving a zero gradient.

**Check 2: Is the monitor actually capturing signal?** Extract the FOM-relevant amplitude at the mode monitor on the initial design. If it returns zero, there is nothing for the adjoint to differentiate. Common causes: monitor placed in the wrong location, waveguide mode not supported at the given wavelength, or monitor normal direction inverted.

**Check 3: Is there an autograd-incompatible operation in the FOM?** Operations on xarray DataArrays, NumPy integer indexing, or in-place array modification can silently break the autograd graph and return zero gradients without an error. Extract all scalar values from DataArrays before computing the FOM, and avoid in-place operations on autograd-tracked arrays.

### Symptom: gradient is non-zero but optimization does not improve

**Check: Is the gradient pointing the right direction?** Do a finite-difference check on a small number of parameters. Perturb `ρ[i,j]` by ±ε and compute `(J(ρ+ε) - J(ρ-ε)) / 2ε`. Compare to the adjoint gradient at `[i,j]`. Agreement to 1–2 significant figures confirms the gradient is correct. Disagreement by a sign indicates the adjoint is computing the wrong sign (e.g., maximization objective coded as minimization, or vice versa).

**Check: Is the learning rate appropriate?** If `lr × |gradient|` is much smaller than `1e-3`, the update steps are negligibly small and optimization will appear flat. Raise the learning rate by 5–10× and see if loss starts moving.

---

## 11. Validation: always go beyond the FOM

The FOM is a proxy for what you actually want. Optimizing it perfectly does not guarantee the device works as intended. Always verify against physical observables that are not part of the FOM.

### Forward simulation with each channel

After optimization, run a clean forward simulation for each input source independently (not the adjoint run — a dedicated evaluation forward run). Extract the complex mode amplitudes at each output. This gives you:
- **Coupling efficiency per channel:** total power coupled from each source into all outputs. Should be consistent with what the FOM was rewarding.
- **Crosstalk:** how much power from source A leaks into channels intended for B, C, D. Should be low even though it appeared in the FOM — if it is not low, the FOM weight was insufficient.
- **Phase encoding:** for devices that rely on phase (e.g., mode sorters), print the relative phases across channels. Verify they have the expected structure.

### Reciprocity / time-reversal check

Optical reciprocity is a powerful validation tool that is independent of the FOM. If your device routes source A to channel X, then driving channel X with the conjugate amplitude should reconstruct source A in the far field. Running this time-reversal check gives you a physical figure of merit — far-field reconstruction fidelity — that is completely independent of the optimization process. A device that scores well on the FOM but fails time-reversal has a subtle FOM mismatch.

### Test on a design the FOM has never seen

If you have any degrees of freedom that were not optimized (wavelength, polarization, input angle range), test performance there. The optimizer will always exploit any loophole in the FOM. If the FOM was evaluated only at a single wavelength, the device may be narrowband in a way that the FOM score does not reveal. Sweep wavelength and plot efficiency vs. wavelength on the final design before reporting results.

---

## 12. Common failure modes: quick-reference table

| Symptom | Most likely cause | First thing to try |
|---|---|---|
| Loss flat from iteration 0 | Zero gradient (source not coupling or broken autograd graph) | Run forward sim, check field in design region; extract FOM terms manually |
| Loss drops but stays high | Local minimum; FOM landscape has a poor basin | Restart from different random seed; try different initial β |
| Loss good, validation fails | FOM does not capture the right physics | Add validation metric to FOM or adjust weights; check for degenerate solutions |
| Design is all-air or all-filled at end | Trivial optimizer escape route | Add power-floor term to FOM; check fabrication penalty magnitude |
| Gray design at high β | β_max too low, filter radius too large | Increase β_max to 50+; reduce filter radius |
| Connectivity lost at waveguide interface | Interface buffer too narrow or wrongly positioned | Widen forced-ρ=1 mask; verify mask positions match waveguide stubs |
| Optimizer diverges (loss increases) | Learning rate too high | Reduce lr by 2×; add gradient clipping |
| Mirror-pair residuals large | Wrong `mirror_sign` or asymmetric source | Rerun audit, fix source geometry, or disable symmetry trade |
| High efficiency, high crosstalk | `λ_orth` too small | Increase `λ_orth` by 3–5× |
| Low efficiency, low crosstalk | `λ_orth` too large; trivial zero-coupling solution | Reduce `λ_orth`; add explicit efficiency floor |
| Resumed run has cold-start transient | Optimizer state not saved in checkpoint | Save full optax state; if already happened, let it run a few extra iterations |
| Cost estimate much higher than expected | Accidental global fine-mesh override | Check `GridSpec` override structures; fine mesh should only cover design region |

---

## 13. Mindset: what inverse design actually is

Inverse design does not find the globally optimal solution. It finds a local minimum of the FOM landscape that is reachable from your initial condition via gradient descent. The design you get depends on:

- Your initial parameters (random seed)
- The FOM (which physical behaviors you reward and penalize)
- The β annealing schedule (how much topological freedom the optimizer had)
- The fabrication constraints (what designs are even representable)

This means two things in practice:

**Restarting is cheap relative to debugging.** If a run clearly converges to a poor local minimum (high crosstalk, low efficiency, disconnected design), sometimes the right move is to restart with a different random seed rather than try to escape the minimum. Try 3–5 random seeds before concluding the FOM or setup is wrong.

**The FOM is a design decision.** Every term you put in the objective encodes a value judgment about what matters. If you optimize for efficiency and then discover crosstalk is unacceptable, the answer is not to run more iterations — it is to go back and add crosstalk to the FOM. The optimizer will find exactly what you asked for, no more and no less. Make sure you asked for the right thing.
