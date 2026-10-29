import Std

namespace P3.DEV_REPRESENTATION_V3

inductive Mark where
  | a
  | b
deriving DecidableEq, Repr

open Mark

inductive Related : List Mark → List Mark → Prop where
  | refl (w) : Related w w
  | exchange (p s) : Related (p ++ [a, b, a] ++ s) (p ++ [b, a, b] ++ s)
  | symm {u v} : Related u v → Related v u
  | trans {u v w} : Related u v → Related v w → Related u w

end P3.DEV_REPRESENTATION_V3
