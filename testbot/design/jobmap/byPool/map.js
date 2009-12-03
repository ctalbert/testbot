function(doc) {
  if (doc.type == 'jobmap') {
      emit(doc.pool, doc);
  }
}
