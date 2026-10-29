import World.Base

namespace P3.DEV_REPRESENTATION_V3
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
    ([a, a, b, b] : List Mark).length = [a, b, a, b].length ∧
    countA [a, a, b, b] = countA [a, b, a, b] := by decide

theorem first_sibling_same_statistics :
    ([a, b, b, a] : List Mark).length = [b, a, a, b].length ∧
    countA [a, b, b, a] = countA [b, a, a, b] := by decide

theorem second_sibling_same_statistics :
    ([a, a, a, b, b, b] : List Mark).length = [a, b, a, b, a, b].length ∧
    countA [a, a, a, b, b, b] = countA [a, b, a, b, a, b] := by decide

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
    bitRun [a, a, b, b] (true, false) ≠ bitRun [a, b, a, b] (true, false) := by decide

theorem bit_cannot_distinguish_first_sibling (q : Bool × Bool) :
    bitRun [a, b, b, a] q = bitRun [b, a, a, b] q := by
  rcases q with ⟨x, y⟩
  cases x <;> cases y <;> decide

#print axioms nonempty_dynamics
#print axioms nontrivial_dynamics
#print axioms contextual_dynamics
#print axioms length_conservation
#print axioms count_not_conserved
#print axioms visible_same_statistics
#print axioms first_sibling_same_statistics
#print axioms second_sibling_same_statistics
#print axioms bit_representation_valid
#print axioms bit_distinguishes_visible_core
#print axioms bit_cannot_distinguish_first_sibling

end P3.DEV_REPRESENTATION_V3
