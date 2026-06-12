(ns rpg-assistant.web.subs
  (:require [re-frame.core :as rf]))

(rf/reg-sub
 :pdf-panel
 (fn [db _]
   (get-in db [:pdf-panel] {:open false :page nil :highlight nil})))

(rf/reg-sub
 :pdf-mobile-open
 (fn [db _]
   (:pdf-mobile-open db false)))

(rf/reg-sub
 :pdf-visible?
 :<- [:pdf-panel]
 (fn [panel _]
   (and (:open panel) (some? (:page panel)))))
