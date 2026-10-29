import World.Base

namespace P3.CAL2_T1_6A99B5D87E404DF3

universe u

theorem oracle_bridge {α : Type u}
    {R0 R1 R2 R3 R4 : α → α → Prop}
    {P : Q_jiburo → α → Prop}
    (rules : Q_tumuho R0 R1 R2 R3 R4 P)
    {start finish : Q_jiburo} {x z : α}
    (path : Q_gajayo R0 R1 R2 R3 R4 start x finish z) (hx : P start x) :
    P finish z := by
  induction path with
  | q_kebida pointMode point => exact hx
  | q_biluva edge tail ih => exact ih (rules.q_yuqipo _ _ edge hx)
  | q_jovobo edge tail ih => exact ih (rules.q_musiba _ _ edge hx)
  | q_temifa edge tail ih => exact ih (rules.q_fivigi _ _ edge hx)
  | q_yalaja edge tail ih => exact ih (rules.q_dociru _ _ edge hx)
  | q_kepeza edge tail ih => exact ih (rules.q_hudoju _ _ edge hx)
  | q_qarocu first second ihFirst ihSecond => exact ihSecond (ihFirst hx)
  | q_civiva first second third ihFirst ihSecond ihThird =>
      exact ihThird (ihSecond (ihFirst hx))

end P3.CAL2_T1_6A99B5D87E404DF3
