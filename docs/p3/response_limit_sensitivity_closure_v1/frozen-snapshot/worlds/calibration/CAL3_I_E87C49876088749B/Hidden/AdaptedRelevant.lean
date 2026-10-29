import World.Base

namespace P3.CAL3_I_E87C49876088749B.Adapted

def measure (s : State) : Int := (s.x - (-2)) * (s.z - (-4)) - (s.y - (1)) * (s.y - (1))

theorem step_measure {s t : State} (h : Step s t) : measure s = measure t := by
  cases h <;> simp only [measure, move1, move2, move3, move4] <;> grind

theorem bridge {s t : State} (h : Reaches s t) : measure s = measure t := by
  induction h with
  | refl => rfl
  | tail _ step ih => exact ih.trans (step_measure step)

end P3.CAL3_I_E87C49876088749B.Adapted
