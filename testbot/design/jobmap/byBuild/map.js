function(doc) {
  if (doc.type == 'jobmap') {
      emit(doc.build,doc);
  }
}
