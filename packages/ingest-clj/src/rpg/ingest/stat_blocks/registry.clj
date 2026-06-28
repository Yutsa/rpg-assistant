(ns rpg.ingest.stat-blocks.registry
  (:require [clojure.string :as str]
            [rpg.ingest.stat-blocks.cof2]
            [rpg.ingest.stat-blocks.core :as core]
            [rpg.ingest.stat-blocks.generic]))

(def ^:private registered-profiles [:cof2 :generic])

(def ^:private alias->profile
  {"cof2" :cof2
   "cof 2" :cof2
   "chroniques oubliées fantasy 2" :cof2
   "chroniques oubliees fantasy 2" :cof2
   "chroniques oubliées" :cof2
   "chroniques oubliees" :cof2
   "generic" :generic})

(defn resolve-profile
  "Resolve game-system string or auto-detect from pages → profile keyword."
  [game-system pages]
  (let [normalized (when game-system (-> game-system str/lower-case str/trim))]
    (cond
      (contains? alias->profile normalized) (alias->profile normalized)
      :else (or (some (fn [profile-id]
                        (when (and (not= profile-id :generic)
                                   (core/matches-document? profile-id pages))
                          profile-id))
                      registered-profiles)
                :generic))))
