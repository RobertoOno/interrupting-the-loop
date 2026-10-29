import World.Base

namespace P3.CAL2_T1_6A99B5D87E404DF3

def Holdout1Statement : Prop :=
  ∀ (α : Type) (R0 R1 R2 R3 R4 : α → α → Prop)
    (P : Q_jiburo → α → Prop),
    Q_tumuho R0 R1 R2 R3 R4 P →
    ∀ (x y z : α),
      Q_gajayo R0 R1 R2 R3 R4 .q_licagu x .q_zotibu y →
      Q_gajayo R0 R1 R2 R3 R4 .q_zotibu y .q_noseke z →
      P .q_licagu x → P .q_noseke z

end P3.CAL2_T1_6A99B5D87E404DF3
