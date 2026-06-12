(ns rpg-assistant-web.core
  (:require [replicant.alias :as alias]
            [replicant.dom :as r]
            [rpg-assistant-web.events :as events]
            [rpg-assistant-web.router :as router]
            [rpg-assistant-web.state :as state]
            [rpg-assistant-web.views :as views]))

(defn- render! []
  (r/render (js/document.getElementById "app")
            (views/render @state/store)
            {:alias-data {:routes router/routes}}))

(defn routing-anchor [attrs children]
  (let [routes (-> attrs :replicant/alias-data :routes)
        href (when-let [loc (:ui/location attrs)]
               (router/location->url routes loc))]
    (into [:a (cond-> attrs href (assoc :href href))]
          children)))

(defn- find-target-href [e]
  (some-> e .-target
          (.closest "a")
          (.getAttribute "href")))

(defn- route-click [e]
  (let [href (find-target-href e)]
    (when-let [location (router/url->location router/routes href)]
      (.preventDefault e)
      (.pushState js/history nil "" href)
      (swap! state/store assoc :location location)
      (render!))))

(defn- on-popstate [_e]
  ;; Le navigateur a changé d'URL (Retour / Avancer) sans recharger la page :
  ;; on resynchronise :location dans le store puis on re-rend toute l'UI.
  (swap! state/store assoc :location (router/current-location))
  (render!))

(defn- install-routing! []
  ;; Clics sur les liens internes → pushState + render (tutoriel Replicant routing).
  (js/document.body.addEventListener "click" route-click)
  ;; Bouton Retour / Avancer → popstate → resync :location + render.
  (.addEventListener js/window "popstate" on-popstate))

(defonce routing-installed?
  (do
    (alias/register! :ui/a routing-anchor)
    (install-routing!)
    true))

(defn ^{:dev/after-load true :export true} reload! []
  (render!))

(defn ^:export init! []
  routing-installed?
  (events/set-render! render!)
  (r/set-dispatch! events/dispatch-event!)
  (swap! state/store assoc :location (router/current-location))
  (events/load-campaigns!)
  (render!))
