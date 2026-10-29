import Hidden.Oracle
namespace P3.CAL3_I_E87C49876088749B
theorem nonempty_dynamics : Reaches start (move1 start) :=
  Reaches.tail (Reaches.refl start) (Step.first start)
theorem nontrivial_dynamics : start ≠ move1 start := by decide
theorem inverse_round_trip : move2 (move1 start) = start ∧ move4 (move3 start) = start := by decide
theorem initial_conserved_value : balance start = 13 := by decide
def comparisonSeed (d n : Int) : State := ⟨n * n + d + (-2), n + (1), 1 + (-4)⟩
theorem comparison_balance (d n : Int) : balance (comparisonSeed d n) = d := by
  grind [balance, comparisonSeed]
theorem different_components (d n : Int) (hne : d ≠ 13) : ¬ Reaches start (comparisonSeed d n) := by
  intro h
  have conserved := oracle_bridge h
  rw [initial_conserved_value, comparison_balance] at conserved
  exact hne conserved.symm
theorem excludes_original_development (n : Int) : ¬ Reaches start (comparisonSeed 1 n) :=
  different_components 1 n (by decide)
end P3.CAL3_I_E87C49876088749B

#print axioms P3.CAL3_I_E87C49876088749B.nonempty_dynamics
#print axioms P3.CAL3_I_E87C49876088749B.nontrivial_dynamics
#print axioms P3.CAL3_I_E87C49876088749B.inverse_round_trip
#print axioms P3.CAL3_I_E87C49876088749B.initial_conserved_value
#print axioms P3.CAL3_I_E87C49876088749B.comparison_balance
#print axioms P3.CAL3_I_E87C49876088749B.different_components
#print axioms P3.CAL3_I_E87C49876088749B.excludes_original_development
