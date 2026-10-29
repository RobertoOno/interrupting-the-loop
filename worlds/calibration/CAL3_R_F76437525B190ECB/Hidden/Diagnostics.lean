import World.Base

namespace P3.CAL3_R_F76437525B190ECB
open Mark

theorem nonempty_dynamics : Related [a, b, a] [b, a, b] := Related.exchange [] []

theorem nontrivial_dynamics : ([a, b, a] : List Mark) ≠ [b, a, b] := by decide

theorem contextual_dynamics (p s : List Mark) :
    Related (p ++ [a, b, a] ++ s) (p ++ [b, a, b] ++ s) := Related.exchange p s

theorem length_conservation {u v : List Mark} (h : Related u v) : u.length = v.length := by
  induction h with
  | refl => rfl
  | exchange => simp
  | symm _ ih => exact ih.symm
  | trans _ _ ih1 ih2 => exact ih1.trans ih2

def countA (w : List Mark) : Nat := (w.filter (fun m => m == a)).length

theorem count_not_conserved :
    ∃ u v : List Mark, Related u v ∧ countA u ≠ countA v :=
  ⟨[a, b, a], [b, a, b], nonempty_dynamics, by decide⟩

theorem visible_same_statistics :
    ([a, a, b, b, b, a] : List Mark).length = [b, a, a, b, a, b].length ∧
    countA [a, a, b, b, b, a] = countA [b, a, a, b, a, b] := by decide

theorem first_sibling_same_statistics :
    ([a, a, b, b, a, b, b, a] : List Mark).length = [b, a, a, a, b, b, a, b].length ∧
    countA [a, a, b, b, a, b, b, a] = countA [b, a, a, a, b, b, a, b] := by decide

theorem second_sibling_same_statistics :
    ([a, a, b, b, a, b, a, b] : List Mark).length = [b, a, a, a, b, b, b, a].length ∧
    countA [a, a, b, b, a, b, a, b] = countA [b, a, a, a, b, b, b, a] := by decide

def bitAction : Mark → Bool × Bool → Bool × Bool
  | a, (x, y) => (x ^^ y, y)
  | b, (x, y) => (x, y ^^ x)

def bitRun : List Mark → Bool × Bool → Bool × Bool
  | [], q => q
  | m :: w, q => bitRun w (bitAction m q)

theorem bit_exchange (q : Bool × Bool) : bitRun [a, b, a] q = bitRun [b, a, b] q := by
  rcases q with ⟨x, y⟩
  cases x <;> cases y <;> decide

theorem bit_append (u v : List Mark) (q : Bool × Bool) :
    bitRun (u ++ v) q = bitRun v (bitRun u q) := by
  induction u generalizing q with
  | nil => rfl
  | cons m u ih => exact ih (bitAction m q)

theorem bit_representation_valid {u v : List Mark} (h : Related u v) (q : Bool × Bool) :
    bitRun u q = bitRun v q := by
  induction h generalizing q with
  | refl => rfl
  | exchange p s =>
      simp only [bit_append]
      exact congrArg (bitRun s) (bit_exchange (bitRun p q))
  | symm _ ih => exact (ih q).symm
  | trans _ _ ih1 ih2 => exact (ih1 q).trans (ih2 q)

theorem bit_distinguishes_visible_core :
    bitRun [a, a, b, b, b, a] (true, false) ≠ bitRun [b, a, a, b, a, b] (true, false) := by decide

theorem bit_cannot_distinguish_first_sibling (q : Bool × Bool) :
    bitRun [a, a, b, b, a, b, b, a] q = bitRun [b, a, a, a, b, b, a, b] q := by
  rcases q with ⟨x, y⟩
  cases x <;> cases y <;> decide


end P3.CAL3_R_F76437525B190ECB

#print axioms P3.CAL3_R_F76437525B190ECB.nonempty_dynamics
#print axioms P3.CAL3_R_F76437525B190ECB.nontrivial_dynamics
#print axioms P3.CAL3_R_F76437525B190ECB.contextual_dynamics
#print axioms P3.CAL3_R_F76437525B190ECB.length_conservation
#print axioms P3.CAL3_R_F76437525B190ECB.count_not_conserved
#print axioms P3.CAL3_R_F76437525B190ECB.visible_same_statistics
#print axioms P3.CAL3_R_F76437525B190ECB.first_sibling_same_statistics
#print axioms P3.CAL3_R_F76437525B190ECB.second_sibling_same_statistics
#print axioms P3.CAL3_R_F76437525B190ECB.bit_exchange
#print axioms P3.CAL3_R_F76437525B190ECB.bit_append
#print axioms P3.CAL3_R_F76437525B190ECB.bit_representation_valid
#print axioms P3.CAL3_R_F76437525B190ECB.bit_distinguishes_visible_core
#print axioms P3.CAL3_R_F76437525B190ECB.bit_cannot_distinguish_first_sibling
