namespace P3.CAL2_T1_6A99B5D87E404DF3

universe u

inductive Q_jiburo where
  | q_noseke
  | q_licagu
  | q_nuyiqu
  | q_zotibu
  | q_gomuna

inductive Q_gajayo {α : Type u}
    (R0 R1 R2 R3 R4 : α → α → Prop) :
    Q_jiburo → α → Q_jiburo → α → Type u where
  | q_kebida (pointMode : Q_jiburo) (point : α) :
      Q_gajayo R0 R1 R2 R3 R4 pointMode point pointMode point
  | q_biluva {x y : α} {finish : Q_jiburo} {z : α} :
      R0 x y → Q_gajayo R0 R1 R2 R3 R4 .q_licagu y finish z →
      Q_gajayo R0 R1 R2 R3 R4 .q_noseke x finish z
  | q_jovobo {x y : α} {finish : Q_jiburo} {z : α} :
      R1 x y → Q_gajayo R0 R1 R2 R3 R4 .q_nuyiqu y finish z →
      Q_gajayo R0 R1 R2 R3 R4 .q_licagu x finish z
  | q_temifa {x y : α} {finish : Q_jiburo} {z : α} :
      R2 x y → Q_gajayo R0 R1 R2 R3 R4 .q_zotibu y finish z →
      Q_gajayo R0 R1 R2 R3 R4 .q_nuyiqu x finish z
  | q_yalaja {x y : α} {finish : Q_jiburo} {z : α} :
      R3 x y → Q_gajayo R0 R1 R2 R3 R4 .q_gomuna y finish z →
      Q_gajayo R0 R1 R2 R3 R4 .q_zotibu x finish z
  | q_kepeza {x y : α} {finish : Q_jiburo} {z : α} :
      R4 x y → Q_gajayo R0 R1 R2 R3 R4 .q_noseke y finish z →
      Q_gajayo R0 R1 R2 R3 R4 .q_gomuna x finish z
  | q_qarocu {start middle finish : Q_jiburo} {x y z : α} :
      Q_gajayo R0 R1 R2 R3 R4 start x middle y →
      Q_gajayo R0 R1 R2 R3 R4 middle y finish z →
      Q_gajayo R0 R1 R2 R3 R4 start x finish z
  | q_civiva {m0 m1 m2 m3 : Q_jiburo} {w x y z : α} :
      Q_gajayo R0 R1 R2 R3 R4 m0 w m1 x →
      Q_gajayo R0 R1 R2 R3 R4 m1 x m2 y →
      Q_gajayo R0 R1 R2 R3 R4 m2 y m3 z →
      Q_gajayo R0 R1 R2 R3 R4 m0 w m3 z

structure Q_tumuho {α : Type u}
    (R0 R1 R2 R3 R4 : α → α → Prop)
    (P : Q_jiburo → α → Prop) : Prop where
  q_yuqipo : ∀ x y, R0 x y → P .q_noseke x → P .q_licagu y
  q_musiba : ∀ x y, R1 x y → P .q_licagu x → P .q_nuyiqu y
  q_fivigi : ∀ x y, R2 x y → P .q_nuyiqu x → P .q_zotibu y
  q_dociru : ∀ x y, R3 x y → P .q_zotibu x → P .q_gomuna y
  q_hudoju : ∀ x y, R4 x y → P .q_gomuna x → P .q_noseke y

end P3.CAL2_T1_6A99B5D87E404DF3
