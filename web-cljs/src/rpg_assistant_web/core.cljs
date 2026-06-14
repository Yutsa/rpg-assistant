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
        loc (:ui/location attrs)]
    (into [:a (cond-> attrs
                loc
                (assoc :href (router/location->url routes loc)))]
          children)))

(defn- find-target-href [e]
  (some-> e .-target
          (.closest "a")
          (.getAttribute "href")))

(defn- sync-location! []
  (swap! state/store assoc :location (router/current-location)))

(defn- route-click [e]
  (let [href (find-target-href e)]
    (when-let [location (router/url->location router/routes href)]
      (.preventDefault e)
      (let [url (router/location->url router/routes location)]
        (.pushState js/history nil "" url)
        (swap! state/store assoc :location location)
        (render!)))))

(defn- on-popstate [_e]
  ;; Le navigateur a changé d'URL (Retour / Avancer) sans recharger la page :
  ;; on resynchronise :location dans le store puis on re-rend toute l'UI.
  (sync-location!)
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

(defn- normalize-browser-url! []
  (when (= "/index.html" (.-pathname js/location))
    (.replaceState js/history nil "" "/")))

(defn ^{:dev/after-load true :export true} reload! []
  (sync-location!)
  (render!))

(defn ^:export init! []
  routing-installed?
  (events/set-render! render!)
  (r/set-dispatch! events/dispatch-event!)
  (normalize-browser-url!)
  (sync-location!)
  (events/load-campaigns!)
  (render!))
