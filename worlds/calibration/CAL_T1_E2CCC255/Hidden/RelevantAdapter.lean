import World.Base

namespace P3.CAL_T1_E2CCC255

universe u

theorem relevant_adapter_bridge {α : Type u} {R : α → α → Prop} {P : α → Prop}
    (h : q_tiwiza R P) {x z : α}
    (route : Q_direra R x z) (hx : P x) : P z := by
  induction route with
  | q_dibuce point => exact hx
  | q_vucofi hxy tail ih => exact ih (h _ _ hxy hx)

end P3.CAL_T1_E2CCC255
