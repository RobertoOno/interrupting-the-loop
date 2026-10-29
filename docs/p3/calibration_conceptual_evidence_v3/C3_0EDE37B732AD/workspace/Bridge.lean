import World.Base

namespace P3.CAL3_R_F76437525B190ECB
open Mark

abbrev Point := Int × Int

def action : Mark → Point → Point
  | a, (x, y) => (x + y, y)
  | b, (x, y) => (x, y - x)

def inverseAction : Mark → Point → Point
  | a, (x, y) => (x - y, y)
  | b, (x, y) => (x, y + x)

theorem action_inverse (m : Mark) (q : Point) : action m (inverseAction m q) = q := by
  cases m <;> cases q <;> simp [action, inverseAction]

theorem inverse_action (m : Mark) (q : Point) : inverseAction m (action m q) = q := by
  cases m <;> cases q <;> simp [action, inverseAction]

def run : List Mark → Point → Point
  | [], q => q
  | m :: w, q => run w (action m q)

def undo : List Mark → Point → Point
  | [], q => q
  | m :: w, q => inverseAction m (undo w q)

theorem run_append (u v : List Mark) (q : Point) : run (u ++ v) q = run v (run u q) := by
  induction u generalizing q with
  | nil => rfl
  | cons m u ih => exact ih (action m q)

theorem run_undo (w : List Mark) (q : Point) : run w (undo w q) = q := by
  induction w generalizing q with
  | nil => rfl
  | cons m w ih => simpa only [run, undo, action_inverse] using ih q

theorem undo_run (w : List Mark) (q : Point) : undo w (run w q) = q := by
  induction w generalizing q with
  | nil => rfl
  | cons m w ih => simp only [run, undo, ih, inverse_action]

theorem exchange_action (q : Point) : run [a, b, a] q = run [b, a, b] q := by
  cases q
  simp only [run, action]
  apply Prod.ext <;> dsimp <;> omega

theorem related_action {u v : List Mark} (h : Related u v) (q : Point) : run u q = run v q := by
  induction h generalizing q with
  | refl => rfl
  | exchange p s =>
      simp only [run_append]
      exact congrArg (run s) (exchange_action (run p q))
  | symm _ ih => exact (ih q).symm
  | trans _ _ ih1 ih2 => exact (ih1 q).trans (ih2 q)

theorem oracle_bridge (p s u v : List Mark)
    (h : Related (p ++ u ++ s) (p ++ v ++ s)) (q : Point) : run u q = run v q := by
  have mapped := related_action h (undo p q)
  simp only [run_append, run_undo] at mapped
  have cancelled := congrArg (undo s) mapped
  simpa only [undo_run] using cancelled

end P3.CAL3_R_F76437525B190ECB
