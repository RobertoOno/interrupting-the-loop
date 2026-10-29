import World.ChallengeEvaluation

namespace P3.CAL3_I_E87C49876088749B

def Q (s : State) : Int := (s.y - 1) * (s.y - 1) - (s.x + 2) * (s.z + 4)

theorem Q_step {s t : State} (h : Step s t) : Q t = Q s := by
  cases h <;> simp only [Q, move1, move2, move3, move4] <;> grind

theorem Q_reaches {s t : State} (h : Reaches s t) : Q t = Q s := by
  induction h with
  | refl => rfl
  | tail h1 h2 ih =>
      rw [Q_step h2]; exact ih

theorem sq_nonneg (a : Int) : 0 ≤ a * a := by
  have h : 0 ≤ a ∨ a ≤ 0 := by omega
  rcases h with h | h
  · exact Int.mul_nonneg h h
  · have h' : (0:Int) ≤ -a := by omega
    have h2 := Int.mul_nonneg h' h'
    have e : (-a) * (-a) = a * a := by grind
    rw [e] at h2
    exact h2

theorem evaluation_solution : Holdout1Statement := by
  intro a b h
  have hq := Q_reaches h
  have h1 : Q ⟨a + (-2), b + (1), -a + (-4)⟩ = b * b + a * a := by
    simp only [Q]
    grind
  have h2 : Q start = -13 := by decide
  have h3 : b * b + a * a = -13 := by rw [← h1, hq, h2]
  have h4 : (0:Int) ≤ b * b + a * a := Int.add_nonneg (sq_nonneg b) (sq_nonneg a)
  rw [h3] at h4
  omega

end P3.CAL3_I_E87C49876088749B
