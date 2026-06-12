(ns rpg-assistant.web.events
  (:require [re-frame.core :as rf]
            [rpg-assistant.web.db :as db]))

(rf/reg-event-db
 :init
 (fn [_ _]
   db/default-db))

(rf/reg-event-db
 :pdf/show-source
 (fn [db [_ page highlight]]
   (let [is-narrow? (.-matches (.matchMedia js/window "(max-width: 900px)"))]
     (-> db
         (assoc-in [:pdf-panel] {:open true :page page :highlight highlight})
         (assoc :pdf-mobile-open is-narrow?)))))

(rf/reg-event-db
 :pdf/close
 (fn [db _]
   (-> db
       (assoc-in [:pdf-panel] {:open false :page nil :highlight nil})
       (assoc :pdf-mobile-open false))))

(rf/reg-event-db
 :pdf/set-mobile-open
 (fn [db [_ open?]]
   (assoc db :pdf-mobile-open open?)))
