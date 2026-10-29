import World.Base

namespace P3.CAL_T1_E2CCC255

def VisibleStatement : Prop :=
  ∀ (α : Type) (R : α → α → Prop) (P : α → Prop)
    (x y z : α),
    q_tiwiza R P →
    R x y → Q_direra R y z →
    P x → P z

end P3.CAL_T1_E2CCC255
