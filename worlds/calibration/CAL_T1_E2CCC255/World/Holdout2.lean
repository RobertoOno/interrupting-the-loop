import World.Base

namespace P3.CAL_T1_E2CCC255

def Holdout2Statement : Prop :=
  ∀ (α : Type) (R : α → α → Prop) (P : α → Prop)
    (w x y z : α),
    q_tiwiza R P →
    Q_direra R w x → R x y → Q_direra R y z →
    P w → P z

end P3.CAL_T1_E2CCC255
