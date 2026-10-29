import World.Base

namespace P3.CAL_T1_E2CCC255

universe u

theorem sham_adapter_bridge {α : Type u} {R : α → α → Prop} {P : α → Prop}
    (h : q_tiwiza R P) {x z : α}
    (route : Q_direra R x z) (hz : P z) : P x := by
  induction route with
  | q_dibuce point => exact hz
  | q_vucofi hxy tail ih => exact h _ _ hxy (ih hz)

end P3.CAL_T1_E2CCC255
