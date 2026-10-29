import World.Base

namespace P3.CAL2_T1_6A99B5D87E404DF3

universe u

theorem sham_adapter_bridge {α : Type u}
    {R0 R1 R2 R3 R4 : α → α → Prop}
    {P : Q_jiburo → α → Prop}
    (rules : Q_tumuho R0 R1 R2 R3 R4 P)
    {start finish : Q_jiburo} {x z : α}
    (path : Q_gajayo R0 R1 R2 R3 R4 start x finish z) (hz : P finish z) :
    P start x := by
  induction path with
  | q_kebida pointMode point => exact hz
  | q_biluva edge tail ih => exact rules.q_yuqipo _ _ edge (ih hz)
  | q_jovobo edge tail ih => exact rules.q_musiba _ _ edge (ih hz)
  | q_temifa edge tail ih => exact rules.q_fivigi _ _ edge (ih hz)
  | q_yalaja edge tail ih => exact rules.q_dociru _ _ edge (ih hz)
  | q_kepeza edge tail ih => exact rules.q_hudoju _ _ edge (ih hz)
  | q_qarocu first second ihFirst ihSecond => exact ihFirst (ihSecond hz)
  | q_civiva first second third ihFirst ihSecond ihThird =>
      exact ihFirst (ihSecond (ihThird hz))

end P3.CAL2_T1_6A99B5D87E404DF3
