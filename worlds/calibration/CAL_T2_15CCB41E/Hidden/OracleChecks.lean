import World.ChallengeVisible
import World.Holdout1
import World.Holdout2
import Hidden.Oracle

namespace P3.CAL_T2_15CCB41E

theorem oracle_visible : VisibleStatement := by
  intro α β encode opA opB h a b c d e
  exact oracle_bridge encode opA opB h (visibleTerm a b c d e)

theorem oracle_holdout1 : Holdout1Statement := by
  intro α β encode opA opB h a b c d e f
  exact oracle_bridge encode opA opB h (holdout1Term a b c d e f)

theorem oracle_holdout2 : Holdout2Statement := by
  intro α β encode opA opB h a b c d e f g
  exact oracle_bridge encode opA opB h (holdout2Term a b c d e f g)

#print axioms oracle_bridge
#print axioms oracle_visible
#print axioms oracle_holdout1
#print axioms oracle_holdout2

end P3.CAL_T2_15CCB41E
