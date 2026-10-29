import World.ChallengeVisible
import World.Holdout1
import World.Holdout2
import Hidden.Oracle
namespace P3.CAL2_T2_9E9C8F0211D9DA4F
theorem oracle_visible : VisibleStatement := by
  intro α β encode opA opB h n env a b
  exact oracle_bridge encode opA opB h (.q_xiviyo a b) env (fun i => encode (env i)) (fun _ => rfl)

#print axioms oracle_visible

theorem oracle_holdout1 : Holdout1Statement := by
  intro α β encode opA opB h n env a b
  exact oracle_bridge encode opA opB h (.q_karaka a b) env (fun i => encode (env i)) (fun _ => rfl)

#print axioms oracle_holdout1

theorem oracle_holdout2 : Holdout2Statement := by
  intro α β encode opA opB h n env a b c
  exact oracle_bridge encode opA opB h (.q_xiviyo a (.q_xiviyo b c)) env (fun i => encode (env i)) (fun _ => rfl)

#print axioms oracle_holdout2
#print axioms oracle_bridge
end P3.CAL2_T2_9E9C8F0211D9DA4F
