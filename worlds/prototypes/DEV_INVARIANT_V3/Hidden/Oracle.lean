import World.Base

namespace P3.DEV_INVARIANT_V3

def balance (s : State) : Int := s.x * s.z - s.y * s.y

theorem step_balance {s t : State} (h : Step s t) : balance s = balance t := by
  cases h <;> simp only [balance, move1, move2, move3, move4] <;> grind

theorem oracle_bridge {s t : State} (h : Reaches s t) : balance s = balance t := by
  induction h with
  | refl => rfl
  | tail _ step ih => exact ih.trans (step_balance step)

end P3.DEV_INVARIANT_V3
