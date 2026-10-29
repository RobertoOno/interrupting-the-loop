import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_R_F76437525B190ECB
open Mark

theorem evaluation_solution : Holdout1Statement := by
  intro p s h
  have key := oracle_bridge p s [a, a, b, b, a, b, b, a] [b, a, a, a, b, b, a, b] h
    ((1 : Int), (0 : Int))
  have hne : run [a, a, b, b, a, b, b, a] ((1 : Int), (0 : Int))
      ≠ run [b, a, a, a, b, b, a, b] ((1 : Int), (0 : Int)) := by decide
  exact hne key

end P3.CAL3_R_F76437525B190ECB
