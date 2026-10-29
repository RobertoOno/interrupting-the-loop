namespace S_jifexi

universe u

inductive Q_siboyo where
  | q_nokufo
  | q_vusuzi
  | q_kebipi
  | q_nagiqe
  | q_katuho

inductive Q_lubuyu {α : Type u}
    (S0 S1 S2 S3 S4 : α → α → Prop) :
    Q_siboyo → α → Q_siboyo → α → Type u where
  | q_rawine (pointMode : Q_siboyo) (point : α) :
      Q_lubuyu S0 S1 S2 S3 S4 pointMode point pointMode point
  | q_cuvuyo {x y : α} {finish : Q_siboyo} {z : α} :
      S0 x y → Q_lubuyu S0 S1 S2 S3 S4 .q_vusuzi y finish z →
      Q_lubuyu S0 S1 S2 S3 S4 .q_nokufo x finish z
  | q_curocu {x y : α} {finish : Q_siboyo} {z : α} :
      S1 x y → Q_lubuyu S0 S1 S2 S3 S4 .q_kebipi y finish z →
      Q_lubuyu S0 S1 S2 S3 S4 .q_vusuzi x finish z
  | q_wavaqi {x y : α} {finish : Q_siboyo} {z : α} :
      S2 x y → Q_lubuyu S0 S1 S2 S3 S4 .q_nagiqe y finish z →
      Q_lubuyu S0 S1 S2 S3 S4 .q_kebipi x finish z
  | q_qixica {x y : α} {finish : Q_siboyo} {z : α} :
      S3 x y → Q_lubuyu S0 S1 S2 S3 S4 .q_katuho y finish z →
      Q_lubuyu S0 S1 S2 S3 S4 .q_nagiqe x finish z
  | q_kozoda {x y : α} {finish : Q_siboyo} {z : α} :
      S4 x y → Q_lubuyu S0 S1 S2 S3 S4 .q_nokufo y finish z →
      Q_lubuyu S0 S1 S2 S3 S4 .q_katuho x finish z
  | q_zilegu {start middle finish : Q_siboyo} {x y z : α} :
      Q_lubuyu S0 S1 S2 S3 S4 start x middle y →
      Q_lubuyu S0 S1 S2 S3 S4 middle y finish z →
      Q_lubuyu S0 S1 S2 S3 S4 start x finish z
  | q_hewuda {m0 m1 m2 m3 : Q_siboyo} {w x y z : α} :
      Q_lubuyu S0 S1 S2 S3 S4 m0 w m1 x →
      Q_lubuyu S0 S1 S2 S3 S4 m1 x m2 y →
      Q_lubuyu S0 S1 S2 S3 S4 m2 y m3 z →
      Q_lubuyu S0 S1 S2 S3 S4 m0 w m3 z

structure Q_wuceqi {α : Type u}
    (S0 S1 S2 S3 S4 : α → α → Prop)
    (P : Q_siboyo → α → Prop) : Prop where
  q_risaru : ∀ x y, S0 x y → P .q_vusuzi y → P .q_nokufo x
  q_rotala : ∀ x y, S1 x y → P .q_kebipi y → P .q_vusuzi x
  q_xipese : ∀ x y, S2 x y → P .q_nagiqe y → P .q_kebipi x
  q_yesizu : ∀ x y, S3 x y → P .q_katuho y → P .q_nagiqe x
  q_fotibi : ∀ x y, S4 x y → P .q_nokufo y → P .q_katuho x

theorem solved_bridge {α : Type u}
    {S0 S1 S2 S3 S4 : α → α → Prop}
    {P : Q_siboyo → α → Prop}
    (rules : Q_wuceqi S0 S1 S2 S3 S4 P)
    {start finish : Q_siboyo} {x z : α}
    (path : Q_lubuyu S0 S1 S2 S3 S4 start x finish z) (hz : P finish z) : P start x := by
  induction path with
  | q_rawine pointMode point => exact hz
  | q_cuvuyo edge tail ih => exact rules.q_risaru _ _ edge (ih hz)
  | q_curocu edge tail ih => exact rules.q_rotala _ _ edge (ih hz)
  | q_wavaqi edge tail ih => exact rules.q_xipese _ _ edge (ih hz)
  | q_qixica edge tail ih => exact rules.q_yesizu _ _ edge (ih hz)
  | q_kozoda edge tail ih => exact rules.q_fotibi _ _ edge (ih hz)
  | q_zilegu first second ihFirst ihSecond => exact ihFirst (ihSecond hz)
  | q_hewuda first second third ihFirst ihSecond ihThird =>
      exact ihFirst (ihSecond (ihThird hz))

#print axioms solved_bridge

end S_jifexi
