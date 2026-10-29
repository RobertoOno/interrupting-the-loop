import Hidden.Oracle
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2

namespace P3.CAL3_R_F76437525B190ECB
open Mark

theorem oracle_visible : VisibleStatement := by
  intro p s h
  have mapped := oracle_bridge p s [a, a, b, b, b, a] [b, a, a, b, a, b] h (1, 0)
  exact (by decide : run [a, a, b, b, b, a] (1, 0) ≠ run [b, a, a, b, a, b] (1, 0)) mapped

theorem oracle_holdout1 : Holdout1Statement := by
  intro p s h
  have mapped := oracle_bridge p s [a, a, b, b, a, b, b, a] [b, a, a, a, b, b, a, b] h (1, 0)
  exact (by decide : run [a, a, b, b, a, b, b, a] (1, 0) ≠ run [b, a, a, a, b, b, a, b] (1, 0)) mapped

theorem oracle_holdout2 : Holdout2Statement := by
  intro p s h
  have mapped := oracle_bridge p s [a, a, b, b, a, b, a, b] [b, a, a, a, b, b, b, a] h (1, 0)
  exact (by decide : run [a, a, b, b, a, b, a, b] (1, 0) ≠ run [b, a, a, a, b, b, b, a] (1, 0)) mapped


end P3.CAL3_R_F76437525B190ECB

#print axioms P3.CAL3_R_F76437525B190ECB.oracle_visible
#print axioms P3.CAL3_R_F76437525B190ECB.oracle_holdout1
#print axioms P3.CAL3_R_F76437525B190ECB.oracle_holdout2
