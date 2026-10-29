import World.ChallengeVisible
import World.Holdout1
import World.Holdout2
import Hidden.Oracle

namespace P3.CAL_T1_E2CCC255

theorem oracle_visible : VisibleStatement := by
  intro α R P x y z h hxy route hx
  exact oracle_bridge h route (h x y hxy hx)

theorem oracle_holdout1 : Holdout1Statement := by
  intro α R P x y z h first second hx
  exact oracle_bridge h second (oracle_bridge h first hx)

theorem oracle_holdout2 : Holdout2Statement := by
  intro α R P w x y z h first hxy second hw
  exact oracle_bridge h second (h x y hxy (oracle_bridge h first hw))

#print axioms oracle_bridge
#print axioms oracle_visible
#print axioms oracle_holdout1
#print axioms oracle_holdout2

end P3.CAL_T1_E2CCC255
