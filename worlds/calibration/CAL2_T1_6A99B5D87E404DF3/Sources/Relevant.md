# Solved source world

This independent world establishes transport over an indexed route.

```lean
namespace S_sulomu

universe u

inductive Q_jozomu where
  | q_yoqazu
  | q_rixija
  | q_pigoso
  | q_yuvidi
  | q_yicume

inductive Q_burepi {α : Type u}
    (S0 S1 S2 S3 S4 : α → α → Prop) :
    Q_jozomu → α → Q_jozomu → α → Type u where
  | q_lacasa (pointMode : Q_jozomu) (point : α) :
      Q_burepi S0 S1 S2 S3 S4 pointMode point pointMode point
  | q_jamara {x y : α} {finish : Q_jozomu} {z : α} :
      S0 x y → Q_burepi S0 S1 S2 S3 S4 .q_rixija y finish z →
      Q_burepi S0 S1 S2 S3 S4 .q_yoqazu x finish z
  | q_faxala {x y : α} {finish : Q_jozomu} {z : α} :
      S1 x y → Q_burepi S0 S1 S2 S3 S4 .q_pigoso y finish z →
      Q_burepi S0 S1 S2 S3 S4 .q_rixija x finish z
  | q_vaforu {x y : α} {finish : Q_jozomu} {z : α} :
      S2 x y → Q_burepi S0 S1 S2 S3 S4 .q_yuvidi y finish z →
      Q_burepi S0 S1 S2 S3 S4 .q_pigoso x finish z
  | q_pikene {x y : α} {finish : Q_jozomu} {z : α} :
      S3 x y → Q_burepi S0 S1 S2 S3 S4 .q_yicume y finish z →
      Q_burepi S0 S1 S2 S3 S4 .q_yuvidi x finish z
  | q_loqoya {x y : α} {finish : Q_jozomu} {z : α} :
      S4 x y → Q_burepi S0 S1 S2 S3 S4 .q_yoqazu y finish z →
      Q_burepi S0 S1 S2 S3 S4 .q_yicume x finish z
  | q_hujuyo {start middle finish : Q_jozomu} {x y z : α} :
      Q_burepi S0 S1 S2 S3 S4 start x middle y →
      Q_burepi S0 S1 S2 S3 S4 middle y finish z →
      Q_burepi S0 S1 S2 S3 S4 start x finish z
  | q_jimimu {m0 m1 m2 m3 : Q_jozomu} {w x y z : α} :
      Q_burepi S0 S1 S2 S3 S4 m0 w m1 x →
      Q_burepi S0 S1 S2 S3 S4 m1 x m2 y →
      Q_burepi S0 S1 S2 S3 S4 m2 y m3 z →
      Q_burepi S0 S1 S2 S3 S4 m0 w m3 z

structure Q_qumoxo {α : Type u}
    (S0 S1 S2 S3 S4 : α → α → Prop)
    (P : Q_jozomu → α → Prop) : Prop where
  q_nubaso : ∀ x y, S0 x y → P .q_yoqazu x → P .q_rixija y
  q_qasoha : ∀ x y, S1 x y → P .q_rixija x → P .q_pigoso y
  q_nufava : ∀ x y, S2 x y → P .q_pigoso x → P .q_yuvidi y
  q_pupalu : ∀ x y, S3 x y → P .q_yuvidi x → P .q_yicume y
  q_kucaze : ∀ x y, S4 x y → P .q_yicume x → P .q_yoqazu y

theorem solved_bridge {α : Type u}
    {S0 S1 S2 S3 S4 : α → α → Prop}
    {P : Q_jozomu → α → Prop}
    (rules : Q_qumoxo S0 S1 S2 S3 S4 P)
    {start finish : Q_jozomu} {x z : α}
    (path : Q_burepi S0 S1 S2 S3 S4 start x finish z) (hx : P start x) : P finish z := by
  induction path with
  | q_lacasa pointMode point => exact hx
  | q_jamara edge tail ih => exact ih (rules.q_nubaso _ _ edge hx)
  | q_faxala edge tail ih => exact ih (rules.q_qasoha _ _ edge hx)
  | q_vaforu edge tail ih => exact ih (rules.q_nufava _ _ edge hx)
  | q_pikene edge tail ih => exact ih (rules.q_pupalu _ _ edge hx)
  | q_loqoya edge tail ih => exact ih (rules.q_kucaze _ _ edge hx)
  | q_hujuyo first second ihFirst ihSecond => exact ihSecond (ihFirst hx)
  | q_jimimu first second third ihFirst ihSecond ihThird =>
      exact ihThird (ihSecond (ihFirst hx))

#print axioms solved_bridge

end S_sulomu
```
