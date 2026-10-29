import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_R_F76437525B190ECB
open Mark

theorem evaluation_solution : Holdout1Statement := by
  intro p s h
  have hrun := oracle_bridge p s _ _ h ((1 : Int), (0 : Int))
  simp only [run, action] at hrun
  exact absurd hrun (by decide)

end P3.CAL3_R_F76437525B190ECB
