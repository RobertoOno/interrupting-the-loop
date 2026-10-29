import World.Base

namespace P3.CAL2_T1_6A99B5D87E404DF3

def Holdout2Statement : Prop :=
  ∀ (α : Type) (R0 R1 R2 R3 R4 : α → α → Prop)
    (P : Q_jiburo → α → Prop),
    Q_tumuho R0 R1 R2 R3 R4 P →
    ∀ (w x y z : α),
      R4 w x →
      Q_gajayo R0 R1 R2 R3 R4 .q_noseke x .q_gomuna y →
      R4 y z →
      P .q_gomuna w → P .q_noseke z

end P3.CAL2_T1_6A99B5D87E404DF3
