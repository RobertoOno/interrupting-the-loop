import World.Base

namespace P3.CAL3_I_E87C49876088749B

def balance (s : State) : Int := (s.x - (-2)) * (s.z - (-4)) - (s.y - (1)) * (s.y - (1))

theorem step_balance {s t : State} (h : Step s t) : balance s = balance t := by
  cases h <;> simp only [balance, move1, move2, move3, move4] <;> grind

theorem oracle_bridge {s t : State} (h : Reaches s t) : balance s = balance t := by
  induction h with
  | refl => rfl
  | tail _ step ih => exact ih.trans (step_balance step)

end P3.CAL3_I_E87C49876088749B
