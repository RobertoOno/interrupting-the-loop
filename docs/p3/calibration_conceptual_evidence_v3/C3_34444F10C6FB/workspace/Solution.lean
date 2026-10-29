import World.ChallengeEvaluation

namespace P3.CAL3_I_E87C49876088749B

def Q (s : State) : Int := (s.y - 1) * (s.y - 1) - (s.x + 2) * (s.z + 4)

theorem Q_step {s t : State} (h : Step s t) : Q t = Q s := by
  cases h <;> simp only [Q, move1, move2, move3, move4] <;> grind

theorem reaches_Q {s t : State} (h : Reaches s t) : Q t = Q s := by
  induction h with
  | refl => rfl
  | tail hr hs ih => exact (Q_step hs).trans ih

theorem evaluation_solution : Holdout2Statement := by
  intro a h
  have h1 : Q ⟨a + (-2), a + (1), a + (-4)⟩ = Q start := reaches_Q h
  have h2 : Q (⟨a + (-2), a + (1), a + (-4)⟩ : State) = 0 := by
    simp only [Q]
    grind
  have h3 : Q start = -13 := by decide
  rw [h2, h3] at h1
  exact absurd h1 (by decide)

end P3.CAL3_I_E87C49876088749B
