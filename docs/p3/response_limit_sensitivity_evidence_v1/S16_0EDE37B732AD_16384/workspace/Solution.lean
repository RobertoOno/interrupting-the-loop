import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_R_F76437525B190ECB
open Mark

theorem evaluation_solution : Holdout2Statement := by
  intro p s h
  exact absurd
    (oracle_bridge p s [a, a, b, b, a, b, a, b] [b, a, a, a, b, b, b, a] h ((1 : Int), (0 : Int)))
    (by decide)

end P3.CAL3_R_F76437525B190ECB
