import World.ChallengeEvaluation
import Bridge

namespace P3.CAL2_T2_9E9C8F0211D9DA4F

theorem evaluation_solution : Holdout2Statement := by
  intro α β encode opA opB h n env a b c
  exact oracle_bridge encode opA opB h _ env (fun i => encode (env i)) (fun i => rfl)

end P3.CAL2_T2_9E9C8F0211D9DA4F
