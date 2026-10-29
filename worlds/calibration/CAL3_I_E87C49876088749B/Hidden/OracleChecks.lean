import Hidden.Oracle
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2

namespace P3.CAL3_I_E87C49876088749B

theorem oracle_visible : VisibleStatement := by
  intro b c h
  have conserved := oracle_bridge h
  have nonnegative := Int.sq_nonneg b
  grind [balance, start]

theorem oracle_holdout1 : Holdout1Statement := by
  intro a b h
  have conserved := oracle_bridge h
  have nonnegativeA := Int.sq_nonneg a
  have nonnegativeB := Int.sq_nonneg b
  grind [balance, start]

theorem oracle_holdout2 : Holdout2Statement := by
  intro a h
  have conserved := oracle_bridge h
  grind [balance, start]


end P3.CAL3_I_E87C49876088749B

#print axioms P3.CAL3_I_E87C49876088749B.oracle_visible
#print axioms P3.CAL3_I_E87C49876088749B.oracle_holdout1
#print axioms P3.CAL3_I_E87C49876088749B.oracle_holdout2
