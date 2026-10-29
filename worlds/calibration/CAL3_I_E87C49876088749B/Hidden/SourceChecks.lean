import Hidden.AdaptedRelevant
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2

namespace P3.CAL3_I_E87C49876088749B

theorem adapted_visible : VisibleStatement := by
  intro b c h
  have conserved := Adapted.bridge h
  have nonnegative := Int.sq_nonneg b
  grind [Adapted.measure, start]

theorem adapted_holdout1 : Holdout1Statement := by
  intro a b h
  have conserved := Adapted.bridge h
  have nonnegativeA := Int.sq_nonneg a
  have nonnegativeB := Int.sq_nonneg b
  grind [Adapted.measure, start]

theorem adapted_holdout2 : Holdout2Statement := by
  intro a h
  have conserved := Adapted.bridge h
  grind [Adapted.measure, start]


def shamMeasure (s : State) : Int := (s.z - (-4)) + (s.x - (-2)) + (s.y - (1))


theorem sham_incompatibility : shamMeasure start ≠ shamMeasure (move1 start) := by decide

end P3.CAL3_I_E87C49876088749B

#print axioms P3.CAL3_I_E87C49876088749B.adapted_visible
#print axioms P3.CAL3_I_E87C49876088749B.adapted_holdout1
#print axioms P3.CAL3_I_E87C49876088749B.adapted_holdout2
#print axioms P3.CAL3_I_E87C49876088749B.sham_incompatibility
