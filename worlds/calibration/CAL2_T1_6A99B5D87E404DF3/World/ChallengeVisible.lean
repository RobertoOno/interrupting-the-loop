import World.Base

namespace P3.CAL2_T1_6A99B5D87E404DF3

def VisibleStatement : Prop :=
  ∀ (α : Type) (R0 R1 R2 R3 R4 : α → α → Prop)
    (P : Q_jiburo → α → Prop),
    Q_tumuho R0 R1 R2 R3 R4 P →
    ∀ (w x y z : α),
      Q_gajayo R0 R1 R2 R3 R4 .q_noseke w .q_nuyiqu x →
      R2 x y →
      Q_gajayo R0 R1 R2 R3 R4 .q_zotibu y .q_gomuna z →
      P .q_noseke w → P .q_gomuna z

end P3.CAL2_T1_6A99B5D87E404DF3
