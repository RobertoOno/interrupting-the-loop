import World.ChallengeEvaluation
import Bridge

namespace P3.CAL2_T1_6A99B5D87E404DF3

theorem evaluation_solution : Holdout2Statement := by
  intro α R0 R1 R2 R3 R4 P rules w x y z hwx path hyz hw
  exact rules.q_hudoju _ _ hyz (oracle_bridge rules path (rules.q_hudoju _ _ hwx hw))

end P3.CAL2_T1_6A99B5D87E404DF3
