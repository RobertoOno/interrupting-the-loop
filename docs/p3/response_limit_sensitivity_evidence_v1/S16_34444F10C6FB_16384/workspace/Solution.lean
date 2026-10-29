import World.ChallengeEvaluation

namespace P3.CAL3_I_E87C49876088749B

def Inv (x y z : Int) : Prop :=
  (x % 2 = 0 ∧ y % 2 = 0 ∧ z % 2 = 1) ∨
  (x % 2 = 1 ∧ y % 2 = 1 ∧ z % 2 = 1) ∨
  (x % 2 = 1 ∧ y % 2 = 0 ∧ z % 2 = 0)

theorem inv_step {s t : State} (hst : Step s t) (h : Inv s.x s.y s.z) :
    Inv t.x t.y t.z := by
  cases hst with
  | first => simp only [Inv, move1] at h ⊢; omega
  | second => simp only [Inv, move2] at h ⊢; omega
  | third => simp only [Inv, move3] at h ⊢; omega
  | fourth => simp only [Inv, move4] at h ⊢; omega

theorem inv_reaches {s t : State} (h : Reaches s t) (hs : Inv s.x s.y s.z) :
    Inv t.x t.y t.z := by
  induction h with
  | refl => exact hs
  | tail => rename_i hr hst ih; exact inv_step hst ih

theorem evaluation_solution : Holdout2Statement := by
  intro a h
  have hstart : Inv start.x start.y start.z := by
    unfold Inv start
    decide
  have hfin := inv_reaches h hstart
  simp only [Inv] at hfin
  omega

end P3.CAL3_I_E87C49876088749B
