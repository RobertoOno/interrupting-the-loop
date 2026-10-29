import World.ChallengeVisible
import World.Holdout1
import World.Holdout2
import Hidden.Oracle

namespace P3.CAL2_T1_6A99B5D87E404DF3

theorem oracle_visible : VisibleStatement := by
  intro α R0 R1 R2 R3 R4 P rules w x y z first edge second hw
  exact oracle_bridge rules second (rules.q_fivigi _ _ edge (oracle_bridge rules first hw))

theorem oracle_holdout1 : Holdout1Statement := by
  intro α R0 R1 R2 R3 R4 P rules x y z first second hx
  exact oracle_bridge rules second (oracle_bridge rules first hx)

theorem oracle_holdout2 : Holdout2Statement := by
  intro α R0 R1 R2 R3 R4 P rules w x y z first path last hw
  exact rules.q_hudoju _ _ last (oracle_bridge rules path (rules.q_hudoju _ _ first hw))

#print axioms oracle_bridge
#print axioms oracle_visible
#print axioms oracle_holdout1
#print axioms oracle_holdout2

end P3.CAL2_T1_6A99B5D87E404DF3
