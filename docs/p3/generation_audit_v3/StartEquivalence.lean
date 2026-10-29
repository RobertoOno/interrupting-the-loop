import World.Base

namespace DevelopmentPreflight
open P3.DEV_INVARIANT_V3

def seed (n : Nat) : State := ⟨(n : Int) * (n : Int) + 1, (n : Int), 1⟩

theorem seed_next (n : Nat) : move1 (seed n) = seed (n + 1) := by
  simp only [move1, seed]
  congr 1 <;> grind

theorem seed_previous (n : Nat) : move2 (seed (n + 1)) = seed n := by
  simp only [move2, seed]
  congr 1 <;> grind

theorem reaches_trans {s t u : State} (h : Reaches s t) (k : Reaches t u) : Reaches s u := by
  induction k with
  | refl => exact h
  | tail _ step ih => exact Reaches.tail ih step

theorem from_zero (n : Nat) : Reaches (seed 0) (seed n) := by
  induction n with
  | zero => exact Reaches.refl (seed 0)
  | succ n ih =>
      have step := Reaches.tail ih (Step.first (seed n))
      simpa only [seed_next] using step

theorem to_zero (n : Nat) : Reaches (seed n) (seed 0) := by
  induction n with
  | zero => exact Reaches.refl (seed 0)
  | succ n ih =>
      have step := Reaches.tail (Reaches.refl (seed (n + 1))) (Step.second (seed (n + 1)))
      have back : Reaches (seed (n + 1)) (seed n) := by
        simpa only [seed_previous] using step
      exact reaches_trans back ih

theorem same_reachable_set (n m : Nat) (t : State) : Reaches (seed n) t ↔ Reaches (seed m) t := by
  constructor
  · intro h
    exact reaches_trans (reaches_trans (to_zero m) (from_zero n)) h
  · intro h
    exact reaches_trans (reaches_trans (to_zero n) (from_zero m)) h

#print axioms seed_next
#print axioms seed_previous
#print axioms reaches_trans
#print axioms from_zero
#print axioms to_zero
#print axioms same_reachable_set

end DevelopmentPreflight
