import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_R_F76437525B190ECB
open Mark

theorem evaluation_solution : Holdout2Statement := by
  intro p s h
  have h2 := oracle_bridge p s [a,a,b,b,a,b,a,b] [b,a,a,a,b,b,b,a] h ((1, 0) : Point)
  refine absurd h2 ?_
  decide

end P3.CAL3_R_F76437525B190ECB
