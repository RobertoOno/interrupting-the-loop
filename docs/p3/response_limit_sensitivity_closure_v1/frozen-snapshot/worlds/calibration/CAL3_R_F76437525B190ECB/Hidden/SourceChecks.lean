import Hidden.AdaptedRelevant
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2

namespace P3.CAL3_R_F76437525B190ECB
open Mark

theorem adapted_visible : VisibleStatement := by
  intro p s h
  have mapped := Adapted.bridge p s [a, a, b, b, b, a] [b, a, a, b, a, b] h (0, 1)
  exact (by decide : Adapted.run [a, a, b, b, b, a] (0, 1) ≠ Adapted.run [b, a, a, b, a, b] (0, 1)) mapped

theorem adapted_holdout1 : Holdout1Statement := by
  intro p s h
  have mapped := Adapted.bridge p s [a, a, b, b, a, b, b, a] [b, a, a, a, b, b, a, b] h (0, 1)
  exact (by decide : Adapted.run [a, a, b, b, a, b, b, a] (0, 1) ≠ Adapted.run [b, a, a, a, b, b, a, b] (0, 1)) mapped

theorem adapted_holdout2 : Holdout2Statement := by
  intro p s h
  have mapped := Adapted.bridge p s [a, a, b, b, a, b, a, b] [b, a, a, a, b, b, b, a] h (0, 1)
  exact (by decide : Adapted.run [a, a, b, b, a, b, a, b] (0, 1) ≠ Adapted.run [b, a, a, a, b, b, b, a] (0, 1)) mapped



end P3.CAL3_R_F76437525B190ECB

#print axioms P3.CAL3_R_F76437525B190ECB.adapted_visible
#print axioms P3.CAL3_R_F76437525B190ECB.adapted_holdout1
#print axioms P3.CAL3_R_F76437525B190ECB.adapted_holdout2
