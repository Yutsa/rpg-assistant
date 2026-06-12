(ns rpg-assistant-web.state
  (:require [rpg-assistant-web.router :as router]))

(defonce store
  (atom {:location (router/current-location)
         :campaigns nil
         :campaigns-loading? false
         :campaigns-error nil}))
