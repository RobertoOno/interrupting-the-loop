import Std

namespace Source

inductive Mark where
  | l
  | r
deriving DecidableEq, Repr

open Mark

inductive Related : List Mark → List Mark → Prop where
  | refl (w) : Related w w
  | exchange (p s) : Related (p ++ [l, r, l] ++ s) (p ++ [r, l, r] ++ s)
  | symm {u v} : Related u v → Related v u
  | trans {u v w} : Related u v → Related v w → Related u w

abbrev Point := Int × Int

def action : Mark → Point → Point
  | l, (x, y) => (x, y + x)
  | r, (x, y) => (x - y, y)

def inverseAction : Mark → Point → Point
  | l, (x, y) => (x, y - x)
  | r, (x, y) => (x + y, y)

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

theorem exchange_action (q : Point) : run [l, r, l] q = run [r, l, r] q := by
  cases q
  simp only [run, action] <;> (apply Prod.ext <;> dsimp <;> omega)

theorem related_action {u v : List Mark} (h : Related u v) (q : Point) : run u q = run v q := by
  induction h generalizing q with
  | refl => rfl
  | exchange p s =>
      simp only [run_append]
      exact congrArg (run s) (exchange_action (run p q))
  | symm _ ih => exact (ih q).symm
  | trans _ _ ih1 ih2 => exact (ih1 q).trans (ih2 q)

theorem bridge (p s u v : List Mark)
    (h : Related (p ++ u ++ s) (p ++ v ++ s)) (q : Point) : run u q = run v q := by
  have mapped := related_action h (undo p q)
  simp only [run_append, run_undo] at mapped
  have cancelled := congrArg (undo s) mapped
  simpa only [undo_run] using cancelled

theorem source_solution : ∀ p s, ¬ Related
    (p ++ [l, l, l, r, r, r] ++ s) (p ++ [r, r, r, l, l, l] ++ s) := by
  intro p s h
  have mapped := bridge p s [l, l, l, r, r, r] [r, r, r, l, l, l] h (0, 1)
  exact (by decide : run [l, l, l, r, r, r] (0, 1) ≠ run [r, r, r, l, l, l] (0, 1)) mapped

end Source

#print axioms Source.action_inverse
#print axioms Source.inverse_action
#print axioms Source.run_append
#print axioms Source.run_undo
#print axioms Source.undo_run
#print axioms Source.exchange_action
#print axioms Source.related_action
#print axioms Source.bridge
#print axioms Source.source_solution
