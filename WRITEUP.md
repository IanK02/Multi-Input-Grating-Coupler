# Inverse Design of Mode-Sorter Grating Couplers


## 1. Project goal: from single-channel grating coupler to angular mode sorter

Grating couplers (GCs) are periodic diffractive structures patterned into a dielectric waveguide layer. Their purpose is to bridge two waves of light not propagating in the same plane. One is a free-space Gaussian beam arriving from above the chip at some angle, and the other a guided mode confined to a waveguide on chip. A conventional GC accomplishes this coupling for **one** input direction and routes the captured light into **one** output waveguide. The grating period is chosen to satisfy the Bragg phase-matching condition between the in-plane component of the free-space wavevector and the propagation constant of the slab mode.

![Grating Coupler](writeup_images/GC_diagram.png)

The notebooks `grating_couplers/overlapping_inputs_2_input_backup.ipynb` (two-input variant) and `grating_couplers/overlapping_inputs.ipynb` (four-input variant) generalise this 1-input 1-output picture. A single grating coupler is illuminated by **N** Gaussian beams that are centered over the middle of the GC but arrive at different angles. On the chip side, there are **N** single-mode Si₃N₄ waveguides arranged symmetrically about y = 0. The design problem is to create a device such that each free-space input source produces a **coherent complex amplitude vector** $C_k$ across the N waveguides, and that the N resulting vectors are mutually orthogonal. Orthogonality here is defined as $\langle c_i | c_j \rangle$ (Hermitian Inner Product) between the waveguide-side fingerprints of two different input sources being equal to 0. If this orthogonality condition is satisfied each source can be perfectly reconstructed by injecting $C^*_k$ into the N waveguides with no bleeding into any other source.

![Diagram of the 4-input device](writeup_images/Tidy3dWriteup_Fig1.jpg)

By optical reciprocity, the same device operated in reverse acts as an angular **multiplexer**. Driving the N waveguides simultaneously with the complex conjugates of any one of the fingerprints $C_k$ reconstructs the corresponding free-space beam at the corresponding angle. The notebooks verify this explicitly in their final Time-Reversal Verification sections (Section 4 below). 

**Material system.** Both notebooks operate at a vacuum wavelength of **λ₀ = 0.729 µm**. The device layer is **Si₃N₄ (n = 2.03)** with thickness **w_thick = 0.22 µm**, sitting on a **SiO₂ buried-oxide layer (n = 1.44, thickness 0.752 µm)** atop a Si₃N₄ substrate. 

---

## 2. Inverse design: parameterisation, objective, and the symmetry trade

This device was created using **inverse design**. I highly recommend watching the following [Tidy3D Inverse Design Lectures](https://www.flexcompute.com/tidy3d/learning-center/inverse-design/) up to lecture 4.

After watching the videos the purpose of the methods shown below should make sense. All of these methods can be found in both `grating_couplers/overlapping_inputs_2_input_backup.ipynb` and `grating_couplers/overlapping_inputs.ipynb`.

1. **`enforce_y_symmetry`** - the array is averaged with its y-reversed copy, so ρ(x, y) = ρ(x, −y). This halves the effective parameter count and, critically, makes the device exactly y-mirror symmetric in the continuous limit. This is exploited in Section 3 to cut FDTD cost.
2. **`interface_buffer`** - at the chip-side edge of the design region, the parameter array is forced to ρ = 1 in narrow horizontal strips coincident with each waveguide stub. This guarantees a clean Si₃N₄ connection between the design region and the waveguides regardless of what the optimiser does elsewhere.
3. **`filter_project` × 2** - a conic spatial filter of radius 90 nm is applied, then a smoothed Heaviside projection of sharpness β maps the filtered density toward a binary distribution. The same operation is applied twice in series; the projection sharpness β is annealed from β = 1 (soft, smoothly differentiable) at iteration 10 to β = 30 (effectively binary) over the remaining 50 iterations. The conic filter enforces a minimum feature size of approximately 90 nm and rules out single-pixel artefacts that fabrication could not reproduce.
4. **`rescale`** - the filtered, projected density in [0, 1] is finally mapped linearly to the permittivity range [ε_min, ε_max] = [1.0, 4.12].

The objective function for the **two-input** variant is
$$
J(\rho) \;=\; (|c_{A,\text{top}}|^2 + |c_{A,\text{bot}}|^2) \;+\; (|c_{B,\text{top}}|^2 + |c_{B,\text{bot}}|^2) \;-\; \lambda_{\text{orth}}\,|\langle C_A | C_B\rangle|^2 \;-\; \mathcal{P}_{\text{fab}}(\rho),
$$
where ${C_a, C_b} \space \epsilon \space \Complex^2$ are the complex mode amplitudes recovered at the two waveguide mode monitors when sources A and B are excited, respectively. $\lambda_{orth}=1.0$ is the crosstalk penalty weight, and 𝒫_fab is an erosion–dilation penalty from `tidy3d.plugins.autograd.make_erosion_dilation_penalty` that discourages sub-resolution features. The first two terms reward total coupled power; the third term, which equals the squared magnitude of the Hermitian inner product between the waveguide-side fingerprints, enforces orthogonality between $C_a$ and $C_b$.

For the **four-input** variant the orthogonality term is restructured. The six raw pairwise inner products that would otherwise appear collapse, after a change of basis to symmetric and antisymmetric combinations of each mirror pair, to four independent scalar constraints:
$$
\text{crosstalk} \;=\; (|s_1|^2 - |a_1|^2)^2 \;+\; (|s_2|^2 - |a_2|^2)^2 \;+\; |\langle s_1 | s_2\rangle|^2 \;+\; |\langle a_1 | a_2\rangle|^2,
$$
where `s_1 = (C_A + C_B)/2`, `a_1 = (C_A − C_B)/2`, `s_2 = (C_C + C_D)/2`, `a_2 = (C_C − C_D)/2`. The first two terms enforce equal coupling magnitudes within each mirror pair; the last two enforce orthogonality between the symmetric and antisymmetric subspaces. The total objective adds a coupling-efficiency reward 2(|C_A|² + |C_C|²) and the same fabrication penalty.

**The mirror-symmetry trade.** 

Since `enforce_y_symmetry` makes the device exactly y-mirror symmetric, sources B and D, which are themselves the y-mirrors of sources A and C, produce waveguide-side amplitude vectors that are related to the A and C fingerprints by the index-flip operator M and a global sign `mirror_sign = ±1`:

![All sources](presentation_results/5_18_results/sources.png)

$$
C_B \;=\; \text{mirror\_sign} \cdot M\, C_A, \qquad C_D \;=\; \text{mirror\_sign} \cdot M\, C_C.
$$

The four-input objective function launches only two FDTD simulations per iteration (sources A and C) and derives $C_B$ and $C_D$ from the sim results of sources A and C. Since `flip_y` is implemented in autograd-aware NumPy, gradient information for C_B propagates correctly back through M into the adjoint of $C_A$, and likewise for $C_D$ and $C_C$. An audit cell at the beginning of the notebook runs all four sources once on the initial parameters and prints |$C_B$ ∓ $M·C_A$| / |$C_A$| for both sign conventions; the smaller residual selects `mirror_sign`. This trade halves cloud simulation cost relative to a naive four-source loop, taking it from approximately 4.4 to ~2.2 FlexCredits per iteration.



Optimisation itself uses the **Adam** algorithm from the `optax` library with learning rate 0.2, run for 40-60 iterations. After each Adam update the parameters are clipped to [0, 1], and a checkpoint dictionary containing the loss history, parameter snapshots, gradients, optimiser states, and β schedule is pickled (the .pkl files) to disk so that the loop can resume from any point.

![Example Two-Input Device](presentation_results/5_4_results/design.png)

---

## 3. The Tidy3D workflow

The notebooks make heavy use of the `tidy3d.plugins.autograd` adjoint module. The objective function `obj(design_param, beta)` is wrapped with `autograd.value_and_grad`, and a single call to `obj` executes a complete forward FDTD simulation, captures the mode-monitor amplitudes, computes the scalar loss, and runs the corresponding **adjoint FDTD simulation** in reverse to yield the gradient dJ/dρ over the entire parameter array.

Each FDTD simulation in this project is built by `make_adjoint_sim`. It constructs:

- a computational domain of size approximately 32 µm × 33 µm × 2.0 µm with 0.6·λ PML spacing on all sides;
- three structures: the waveguides, the SiO₂ oxide layer, and the underlying Si₃N₄ substrate 
- a `td.Structure` object with material `td.CustomMedium` whose spatial permittivity profile is the rescaled ρ array, built by `update_design`. This is the design region that is optimized during the optimization loop.
- an automatic grid (`td.GridSpec.auto`) with at least 15 cells per wavelength globally, overridden inside the design region by a `MeshOverrideStructure` that enforces a uniform 20 nm cell. This matches the design-parameter grid so that each ρ pixel maps to exactly one Yee cell;
- exactly one source, an `AstigmaticGaussianBeam` with different x and y waist sizes `(w_x, w_y)` which are computed so that the tilted elliptical footprint at the source plane exactly fills the design region. 

A single iteration consists of: (i) preprocess ρ, (ii) build N/2 to N forward simulations, (iii) submit them to the cloud, (iv) extract complex amplitudes at each mode monitor, (v) form the scalar objective, (vi) execute the adjoint FDTDs to obtain dJ/dρ, (vii) apply the Adam update, (viii) clip and checkpoint. 

With β (the binarizing parameter) annealed from 1 to 30 over the first ~75% of iterations the optimiser is allowed to discover topology while the projection is soft and is then forced to commit to a binary fabricable design as the projection sharpens.

---

## 4. Verification: time-reversal and far-field overlap

Two verifications run on the final design. **Complex amplitude extraction** rebuilds the simulation with each source individually and records `C_A, C_B, …` to four decimal places The absolute values give the per-source coupling efficiency, the relative phases give the encoded angular information, and the overlap between two complex amplitude vectors `|⟨c_i | c_j⟩|` quantifies crosstalk. In the four-input variant the mirror identities are checked on the optimised design. The residuals |C_B − mirror_sign·M·C_A| / |C_A| should be of order 10⁻³ or smaller if the symmetry trade has been achieved succesfully by the optimisation.

The more physical verification is **time-reversal reconstruction**. For each fingerprint $C_k$, a new simulation is built in which N `ModeSource` objects, one at each waveguide, inject Gaussian pulses with amplitudes $C_{k,i}$ and phases $-\angle C_{k,i}$ where k refers to the source and i to an individual waveguide. The value injected at the waveguides is the complex conjugate of the recorded fingerprint for each source, $C^*_k$. A `FieldMonitor` placed 50 nm above the device captures the emitted near field, which is then projected to a Cartesian plane at $z = 100\mu m$  using `tidy3d.FieldProjector.from_near_field_monitors`. The resulting far-field intensity pattern is compared against a reference simulation containing only the original Gaussian source propagating upward through vacuum. The normalised complex overlap integral
$$
\eta_{ij} \;=\; \frac{\left|\iint \mathbf{E}^*_{\text{rev},i} \cdot \mathbf{E}_{\text{ref},j}\, dx\, dy\right|^2}{\left(\iint |\mathbf{E}_{\text{rev},i}|^2\, dx\, dy\right)\left(\iint |\mathbf{E}_{\text{ref},j}|^2\, dx\, dy\right)}
$$
gives values in $[0,1]$ $η_{ii}$ measures reconstruction fidelity for channel i, and $η_{ij}$ for $i ≠ j$ measures channel leakage. A successful device produces a strongly diagonal-dominant $η$ matrix. 

![Farfield results of 2-input device](presentation_results/5_4_results/farfield.png)

---

## 5. Tips for working on this problem

This section captures practical knowledge accumulated through trial and error on this project. It is written for someone who has read Sections 1–4, understands the physics and code at a high level, and now needs to actually run, debug, or extend the optimization without learning everything the hard way.

---

### 5.1 Start with the 2-input case

If you have any ideas that very fundamentally change the design try and get the idea working on the 2-input case before moving to the 4 input or any 2N input case. There are a few reasons for this, given below.

1. **Cheaper.** One FDTD per iteration instead of two (with the symmetry trade), so iteration cost drops by roughly 2×. You can run 40 iterations and see meaningful convergence for a fraction of the cost.
2. **Simpler objective.** There is only one orthogonality constraint: $|\langle C_A | C_B \rangle|^2 = 0$. If something is wrong with your FOM definition, the 2-input case exposes it quickly.
4. **A working 2-input design is useful evidence.** If the 2-input device converges but the 4-input one does not, you know the FDTD setup and source geometry are correct, the problem is in the 4-input objective or constraint algebra.

---
### 5.2 Set bandwidth to atleast 20nm

Bandwidth, called `bw` in the configuration cell defines the bandwidth of the sources used during opitimization. Setting `bw` to atleast 20nm stretches the source out in the time domain. This allows the simulation to hit its early shutoff conidition, the early shutoff condition being when all fields in the simulation have decayed below some bounadry (usually 1e-5) of their original power the simulation will end early. This allow HUGEs savings in cost, often making simulations cost only 8-10% of their estimated cost. 

---

### 5.3 Always run the mirror-symmetry audit before optimization

The symmetry trade (deriving $C_B, C_D$ from $C_A, C_C$ instead of simulating them) can cut FlexCredit expenditure roughly in half. But the trade is only valid if the mode-monitor convention respects y-mirror symmetry on this particular grid, and if the `mirror_sign` (±1) is set correctly.

**Run the audit cell before every optimization run**, not just the first one. It runs all four sources on the current parameter state (the initial or resumed checkpoint) and prints two residuals:

```
+ residual (mirror_sign=+1): |c_B - (+M·c_A)| / |c_A|
- residual (mirror_sign=-1): |c_B - (-M·c_A)| / |c_A|
```

**What good looks like:** the smaller of the two residuals should be below ~10⁻². If it is, the symmetry trade is valid and `mirror_sign` should be set to whichever sign produced the smaller value.

**What bad looks like:** both residuals are large (> 0.1). This usually means the source B is not actually the y-mirror of source A, check the `yz_angle` sign convention for each source, and verify that the waveguide y-positions are symmetric about y=0.

If the audit fails, fall back to running all N sources explicitly per iteration. You will pay 2× in FlexCredits but the gradients will be correct. Never use the symmetry trade with an unvalidated `mirror_sign`, doing so completely undercuts the optimization and your credits will have been wasted.

---

### 5.4 How to read the loss curve

Plot `history_dict['values']` after any run. A healthy optimization has three recognizable phases:

1. **Rapid rise (iterations 0–10, β = 1, soft projection).** The optimizer is working in a smooth, high-dimensional landscape and can make large jumps. Loss should fall quickly. If it does not move at all in the first five iterations, the learning rate is too low or the gradient is numerically zero somewhere.

2. **Plateau and reorganization (β ramp begins, iterations 10–30).** As the projection sharpens, intermediate-density regions are forced toward binary. The loss often temporarily worsens or stalls as the design topology commits. This is normal, do not stop the run here. The temporary stall is the optimizer discovering that the soft topology it found is not quite feasible when binarized.

3. **Slow improvement toward convergence (iterations 30–60).** The design is now mostly binary. The FOM typically asymptotes. If it is still rising steeply at iteration 60, you likely need more iterations.

**Red flag:** FOM goes flat at a high value in phase 1 (before β ramp). This means the optimizer is stuck at the initial condition. Diagnose by checking whether the gradient norm is non-zero (it is in `history_dict['gradients']`). If gradients are tiny, the source is not coupling into the design region at all, verify source geometry and position.

**Red flag:** FOM decreases after β ramp starts and never recovers. This indicates the soft solution was not close to any feasible binary solution. Try delaying the ramp (`beta_ramp_start`) so the optimizer has more time to find a good topology before being forced to commit.

---

### 5.6 How to read the design

**Signs of a healthy design:**
- Clear binary contrast (black = Si₃N₄, white = air, no large gray regions).
- Visible grating-like periodicity along the beam propagation direction (x-axis). This is the Bragg structure responsible for coupling.
- Solid Si₃N₄ connections at all waveguide interface buffer positions, you should see continuous material paths from design region to each waveguide stub.

**Signs of a problematic design:**
- Large gray regions (intermediate ε) persist at high β. This usually means the filter radius is too large relative to the design region, or the β annealing ramp was too slow. The filter is enforcing a minimum feature size that the optimizer cannot satisfy in this region while also satisfying the FOM.
- No connection at a waveguide interface buffer position. The optimizer has eroded the connection. Increase `border_buffer` or widen the forced-Si₃N₄ mask.
- The design looks entirely random (salt-and-pepper noise). The β ramp went too fast or started too early before topology could emerge. Reduce `beta_ramp_start`.

---

### 5.7 Tuning the objective function weights

The objective has three competing terms: efficiency, orthogonality, and fabrication penalty. Small changes here make big differences.

**Efficiency term** (`2(|C_A|² + |C_C|²)`): do not touch the coefficient of 2. It accounts for the B/D symmetric pairs and normalizes the scale properly relative to the orthogonality term.

**Orthogonality penalty** (`λ_orth`): the default is `λ_orth = 1.0`. This is a balanced starting point but is not always optimal:
- If the final design shows high coupling efficiency but large crosstalk (|⟨c_i|c_j⟩| > 0.2), increase `λ_orth` to 2–4. The optimizer has been prioritizing power at the expense of state separation.
- If the final design shows low coupling efficiency and low crosstalk (very small |C_k| values across the board), `λ_orth` is too large relative to the efficiency term. The optimizer has found the trivial solution of coupling nothing to avoid the crosstalk penalty. Reduce `λ_orth` to 0.5–0.8.

**Fabrication penalty** (`𝒫_fab`): the erosion–dilation penalty is applied at fixed weight throughout the run. Its magnitude is automatically normalized to the feature size, so you rarely need to tune it. The main symptom of it being too strong is that the optimizer produces an empty design (all air in the design region). If you see this, reduce the penalty weight or turn it off for the first 20 iterations.

---

### 5.8 The β annealing schedule and why timing matters

The projection sharpness β controls the trade-off between optimizer freedom and design binarness.

**Why soft first:** at β = 1 the optimizer can form large-scale topology, where the grating teeth should roughly be, which y-positions carry which channels, without being distracted by the discretization noise that a sharp projection introduces.

**When to change the timing:**
- If the design has not formed recognizable grating structure by iteration 10 (the design still looks like random noise), delay the ramp start. The optimizer needs more time in the soft regime.
- If the design looks good at iteration during β = 1 regime but degrades during the ramp, the annealing is too fast. Extend the ramp over more iterations.
- If computation budget is limited and you want faster convergence to a feasible (if not optimal) design, start the ramp earlier and ramp to only β = 10. The result will be less binary but faster.

---

### 5.9 The interface buffer: do not underestimate it

The `interface_buffer` function forces `ρ = 1` (full Si₃N₄) in narrow strips at the waveguide coupling positions on left edge of the design region. Without it, the optimizer will sometimes erode the material right at the waveguide mouth, because reducing coupling to a specific waveguide can reduce crosstalk even if it also reduces total efficiency. The result is a design that looks great in the loss curve but has no physical connection to half the waveguides.

**Check the interface buffer visually in every design you evaluate.** Look at the left  200–300 nm of the design region at each waveguide y-position. They should be solidly ρ = 1 in the binarized design.

---

### 5.10 Checkpointing: save everything, resume exactly

Every iteration pickles `history_dict` to disk before the next iteration begins. This means:

- If the cloud job fails mid-iteration (network error, timeout), you lose only that iteration.
- If you want to change some optimization parameter midway, load the checkpoint, modify the parameter, and continue.
- The pickled β schedule allows you to verify exactly what projection sharpness was used at each iteration useful when debugging designs that looked good mid-run but degraded later.

---

### 5.11 Common failure modes and their fixes

| Symptom | Most likely cause | Fix |
|---|---|---|
| FOM flat from iteration 0 | Source not coupling into design region | Verify source position and angle, check that the design region CustomMedium is actually inside the source footprint |
| FOM increases then plateaus early at high value | β ramp started too early, optimizer locked in bad topology | Increase `beta_ramp_start` from 10 to 20, also try restarting from a different random seed |
| Loss improves but crosstalk stays high | `λ_orth` too small | Increase `λ_orth` to 3–5 and restart or continue from checkpoint |
| Empty design (all air) in final result | Fabrication penalty or `λ_orth` too aggressive | Reduce penalty weight, start with `λ_orth = 0.5` and warm up |
| Good efficiency but mirror residuals > 10% | Wrong `mirror_sign` or asymmetric source definition | Rerun audit, verify source B is the exact y-reflection of source A and source D is exact y-reflection of source C in 4-input case|
| Gray regions persist at β = 30 | Filter radius too large for the available design region | Reduce filter radius or enlarge design region |


---

### 5.12 Cost management tips

Cloud FDTD is expensive. A few practices that pay off:

- **Estimate before every run.** Use `web.estimate_cost()` on the initial simulation. If it is higher than expected, a quick fix can be to try and reduce mesh density. Simulation costs scales roughly with x<sup>3</sup> so even a small change can make a big difference.
- **Prototype on a smaller design region.** A 10 µm × 10 µm design at 20 nm resolution has 1/6 the parameters of the full 24 µm × 24 µm region. Use it to test FOM definition changes, debug objective function bugs, and validate the audit cell without committing full-run credits.
- **Do not run the β = 1 phase for more than 25% of iterations.** After that, the topology is set and you are just spending credits refining a topology that will be disrupted by the β ramp anyway. The soft phase exists to find structure, not to converge.
- **Save the optax optimizer state in checkpoints.** Restarting from parameters alone (without optimizer state) throws away Adam's momentum, effectively cold-starting the optimizer. This costs a few warm-up iterations that are wasted computation.