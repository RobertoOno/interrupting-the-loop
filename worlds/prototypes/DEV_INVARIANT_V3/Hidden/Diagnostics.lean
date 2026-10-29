import World.Base

namespace P3.DEV_INVARIANT_V3

theorem nonempty_dynamics : Reaches start ⟨5, 2, 1⟩ :=
  Reaches.tail (Reaches.refl start) (Step.first start)

theorem inverse_round_trip : Reaches start start :=
  Reaches.tail nonempty_dynamics (Step.second ⟨5, 2, 1⟩)

theorem visible_property_not_step_closed :
    ∃ s t : State, Step s t ∧ s.x ≠ 0 ∧ t.x = 0 :=
  ⟨⟨1, 0, -1⟩, ⟨0, -1, -1⟩, Step.first _, by decide, rfl⟩

theorem first_sibling_property_not_step_closed :
    ∃ s t : State, Step s t ∧ s.x + s.z ≠ 0 ∧ t.x + t.z = 0 :=
  ⟨⟨0, 1, -1⟩, ⟨1, 0, -1⟩, Step.first _, by decide, rfl⟩

theorem second_sibling_property_not_step_closed :
    ∃ s t : State, Step s t ∧ (s.x ≠ s.y ∨ s.z ≠ s.y) ∧ t.x = t.y ∧ t.z = t.y :=
  ⟨⟨0, 0, 1⟩, ⟨1, 1, 1⟩, Step.first _, Or.inr (by decide), rfl, rfl⟩

theorem reachable_negative_coordinate : ∃ s, Reaches start s ∧ s.y < 0 :=
  ⟨move4 start, Reaches.tail (Reaches.refl start) (Step.fourth start), by decide⟩

theorem singular_seed_breaks_visible : Reaches ⟨1, 1, 1⟩ ⟨0, 0, 1⟩ :=
  Reaches.tail (Reaches.refl _) (Step.second _)

theorem no_nonzero_linear_conservation (a b c : Int)
    (h1 : ∀ s, a * (move1 s).x + b * (move1 s).y + c * (move1 s).z =
                a * s.x + b * s.y + c * s.z)
    (h3 : ∀ s, a * (move3 s).x + b * (move3 s).y + c * (move3 s).z =
                a * s.x + b * s.y + c * s.z) : a = 0 ∧ b = 0 ∧ c = 0 := by
  have e1 := h1 ⟨0, 1, 0⟩
  have e2 := h1 ⟨0, 0, 1⟩
  have e3 := h3 ⟨1, 0, 0⟩
  simp [move1, move3] at e1 e2 e3
  omega

#print axioms nonempty_dynamics
#print axioms inverse_round_trip
#print axioms visible_property_not_step_closed
#print axioms first_sibling_property_not_step_closed
#print axioms second_sibling_property_not_step_closed
#print axioms reachable_negative_coordinate
#print axioms singular_seed_breaks_visible
#print axioms no_nonzero_linear_conservation

end P3.DEV_INVARIANT_V3
