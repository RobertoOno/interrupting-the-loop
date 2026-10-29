import Hidden.Oracle
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2

namespace P3.DEV_REPRESENTATION_V3
open Mark

theorem oracle_visible : VisibleStatement := by
  intro p s h
  have mapped := oracle_bridge p s [a, a, b, b] [a, b, a, b] h (1, 0)
  exact (by decide : run [a, a, b, b] (1, 0) ≠ run [a, b, a, b] (1, 0)) mapped

theorem oracle_holdout1 : Holdout1Statement := by
  intro p s h
  have mapped := oracle_bridge p s [a, b, b, a] [b, a, a, b] h (1, 0)
  exact (by decide : run [a, b, b, a] (1, 0) ≠ run [b, a, a, b] (1, 0)) mapped

theorem oracle_holdout2 : Holdout2Statement := by
  intro p s h
  have mapped := oracle_bridge p s [a, a, a, b, b, b] [a, b, a, b, a, b] h (1, 0)
  exact (by decide : run [a, a, a, b, b, b] (1, 0) ≠ run [a, b, a, b, a, b] (1, 0)) mapped

#print axioms oracle_bridge
#print axioms oracle_visible
#print axioms oracle_holdout1
#print axioms oracle_holdout2

end P3.DEV_REPRESENTATION_V3
